import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.Building as bd
from pycity_scheduling import util, classes

from .entity_container import EntityContainer
from pycity_scheduling.exception import NonoptimalError


class Building(EntityContainer, bd.Building):
    """
    Extension of pyCity_base class Building for scheduling purposes.

    Notes
    -----
     - exchange of thermal energy is currently not supported / turned off
    """

    def __init__(self, environment, objective='price', name=None,
                 profile_type=None, building_type=None,
                 storage_end_equality=False):
        """Initialize building.

        Parameters
        ----------
        environment : Environment
        objective : str, optional
            Objective for the scheduling. Defaults to 'price'.
            - 'price' : Optimize for the prices given by `prices.tou_prices`.
            - 'co2' : Optimize for the CO2 emissions given by
                      `prices.co2_prices`.
            - 'peak-shaving' : Try to flatten the schedule as much as possible.
            - 'max-consumption' : Try to reduce the maximum of the absolute values
                                  of the schedule as much as possible.
            - 'none' : No objective (leave all flexibility to other
                       participants).
        name : str, optional
            Name for the building.
            If name is None set it to self._long_ID
        profile_type : str, optional
            Thermal SLP profile name
            Requires `method=1`
            - 'HEF' : Single family household
            - 'HMF' : Multi family household
            - 'GBA' : Bakeries
            - 'GBD' : Other services
            - 'GBH' : Accomodations
            - 'GGA' : Restaurants
            - 'GGB' : Gardening
            - 'GHA' : Retailers
            - 'GHD' : Summed load profile business, trade and services
            - 'GKO' : Banks, insurances, public institutions
            - 'GMF' : Household similar businesses
            - 'GMK' : Automotive
            - 'GPD' : Paper and printing
            - 'GWA' : Laundries
        building_type : str, optional
            Build year profile name, the detailed list is implemented in gui.py
            at the beginning of the __init__ function
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        super().__init__(environment)

        self._long_ID = "BD_" + self._ID_string
        if name is None:
            self.name = self._long_ID
        else:
            self.name = name

        self.objective = objective
        self.profile_type = profile_type
        self.building_type = building_type
        self.storage_end_equality = storage_end_equality

    def populate_model(self, model, mode="convex", robustness=None):
        """Add building block to pyomo ConcreteModel.

        Call parent's `populate_model` method and set variables lower
        bounds to `None`. Then call `populate_model` method of the BES
        and all contained apartments and add constraints that the sum
        of their variables for each period period equals the
        corresponding own variable.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        if not self.hasBes:
            raise AttributeError(
                "No BES in %s\nModeling aborted." % str(self)
            )
        super().populate_model(model, mode)
        m = self.model

        def p_equality_rule(model, t):
            return 0 == model.P_Th_vars[t]
        m.P_equality_constr = pyomo.Constraint(m.t, rule=p_equality_rule)

        if robustness is not None and self.bes.hasTes:
            self._create_robust_constraints()



    def update_model(self, mode="", robustness=None):
        super().update_model(mode)

        if robustness is not None and self.bes.hasTes:
            self._update_robust_constraints(robustness)


    def _create_robust_constraints(self):
        m = self.model
        tes_m = self.bes.tes.model
        m.lower_robustness_bounds = pyomo.Param(m.t, mutable=True)
        m.upper_robustness_bounds = pyomo.Param(m.t, mutable=True)

        def e_lower_rule(model, t):
            return tes_m.E_Th_vars[t] >= model.lower_robustness_bounds[t]
        m.lower_robustness_constr = pyomo.Constraint(m.t, rule=e_lower_rule)

        def e_upper_rule(model, t):
            return tes_m.E_Th_vars[t] <= model.upper_robustness_bounds[t]
        m.upper_robustness_constr = pyomo.Constraint(m.t, rule=e_upper_rule)


    def _update_robust_constraints(self, robustness):
        m = self.model
        timestep = self.timer.currentTimestep
        E_Th_Max = self.bes.tes.E_Th_Max
        end_value = self.bes.tes.SOC_Ini * E_Th_Max
        uncertain_P_Th = np.zeros(self.op_horizon)
        P_Th_Demand_sum = np.zeros(self.op_horizon)

        # aggregate demand from all thermal demands
        t1 = timestep
        t2 = timestep + self.op_horizon
        for apartment in self.apartments:
            for entity in apartment.Th_Demand_list:
                if isinstance(entity, classes.SpaceHeating):
                    P_Th_Demand_sum += entity.P_Th_Schedule[t1:t2]

        P_Th_Max_Supply = sum(
            e.P_Th_Nom for e in classes.filter_entities(self, 'heating_devices')
        )

        # Get parameter for robustness conservativeness
        lambda_i, lambda_d = divmod(robustness[0], 1)
        lambda_i = int(lambda_i)
        if lambda_i >= self.op_horizon:
            lambda_i = self.op_horizon - 1
            lambda_d = 1

        for t in self.op_time_vec:
            uncertain_P_Th[t] = min(P_Th_Demand_sum[t] * robustness[1],
                                    P_Th_Max_Supply)
            tmp = sorted(uncertain_P_Th, reverse=True)
            uncertain_E_Th = self.time_slot * (sum(tmp[:lambda_i])
                                               + tmp[lambda_i]*lambda_d)

            # If environment is too uncertain, keep storage on half load
            if uncertain_E_Th >= E_Th_Max / 2:
                m.lower_robustness_bounds[t] = E_Th_Max / 2
                m.upper_robustness_bounds[t] = E_Th_Max / 2
            # standard case in
            elif t < self.op_horizon - 1:
                m.upper_robustness_bounds[t] = E_Th_Max - uncertain_E_Th
                m.lower_robustness_bounds[t] = uncertain_E_Th
            # set storage to uncertain_E_Th or set SOC_End to SOC_Ini to
            # prevent depletion of storage
            else:
                if self.bes.tes.SOC_Ini <= 0.5:
                    end_value = max(end_value, uncertain_E_Th)
                else:
                    end_value = min(end_value, E_Th_Max - uncertain_E_Th)
                m.lower_robustness_bounds[t] = end_value
                m.upper_robustness_bounds[t] = end_value

    def get_lower_entities(self):
        if self.hasBes:
            yield self.bes
        yield from self.apartments
