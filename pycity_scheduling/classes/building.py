import numpy as np
import gurobipy as gurobi
import pycity_base.classes.Building as bd
from pycity_scheduling import util

from .electrical_entity import ElectricalEntity
from .thermal_entity import ThermalEntity
from pycity_scheduling.exception import UnoptimalError


class Building(ElectricalEntity, bd.Building):
    """
    Extension of pycity class Building for scheduling purposes.

    Notes
    -----
     - exchange of thermal energy is currently not supported / turned off
    """

    def __init__(self, environment, objective="price", name=None,
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
            - 'peak_shaving' : Try to flatten the scheudle as much as possible.
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
        super(Building, self).__init__(environment)

        self._long_ID = "BD_" + self._ID_string
        if name is None:
            self.name = self._long_ID
        else:
            self.name = name

        self.objective = objective
        self.profile_type = profile_type
        self.building_type = building_type
        self.storage_end_equality = storage_end_equality

        self.deviation_model = None

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model.

        Call both parent's `populate_model` methods and set variables lower
        bounds to `-gurobi.GRB.INFINITY`. Then call `populate_model` method
        of the BES and all contained apartments and add constraints that the
        sum of their variables for each period period equals the corresponding
        own variable.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(Building, self).populate_model(model, mode)

        P_Th_var_list = []
        P_El_var_list = []
        if not self.hasBes:
            raise AttributeError(
                "No BES in %s\nModeling aborted." % str(self)
            )
        for entity in self.get_lower_entities():
            entity.populate_model(model, mode)
            P_Th_var_list.extend(entity.P_Th_vars)
            P_El_var_list.extend(entity.P_El_vars)

        for t in self.op_time_vec:
            self.P_El_vars[t].lb = -gurobi.GRB.INFINITY
            P_Th_var_sum = gurobi.quicksum(P_Th_var_list[t::self.op_horizon])
            P_El_var_sum = gurobi.quicksum(P_El_var_list[t::self.op_horizon])
            model.addConstr(
                0 == P_Th_var_sum,
                "{0:s}_P_Th_at_t={1}".format(self._long_ID, t)
            )
            model.addConstr(
                self.P_El_vars[t] == P_El_var_sum,
                "{0:s}_P_El_at_t={1}".format(self._long_ID, t)
            )

    def get_objective(self, coeff=1):
        """Objective function of the building.

        Return the objective function of the bulding wheighted with coeff.
        Depending on self.objective build objective function for shape
        shifting, or price / CO2 minimization.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        obj = gurobi.QuadExpr()
        if self.objective == "peak_shaving":
            obj.addTerms(
                [coeff]*self.op_horizon,
                self.P_El_vars,
                self.P_El_vars
            )
        else:
            if self.objective == "price":
                prices = self.environment.prices.tou_prices
            elif self.objective == "co2":
                prices = self.environment.prices.co2_prices
            else:
                # TODO: Print warning.
                prices = np.ones(self.simu_horizon)
            prices = prices[self.op_slice]
            prices = prices * self.op_horizon / sum(prices)
            obj.addTerms(
                coeff * prices,
                self.P_El_vars
            )
        return obj

    def update_model(self, model, mode=""):
        for entity in self.get_lower_entities():
            entity.update_model(model, mode)

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        super(Building, self).update_schedule()
        
        for entity in self.get_lower_entities():
            entity.update_schedule()

    def populate_deviation_model(self, model, mode=""):
        """Populate the deviation model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        """
        super(Building, self).populate_deviation_model(model, mode)

        P_Th_var_list = []
        P_El_var_list = []
        if not self.hasBes:
            raise AttributeError(
                "No BES in %s\nModeling aborted." % str(self)
            )
        for entity in self.get_lower_entities():
            entity.populate_deviation_model(model, mode)
            if isinstance(entity, ThermalEntity):
                P_Th_var_list.append(entity.P_Th_Act_var)
            if isinstance(entity, ElectricalEntity):
                P_El_var_list.append(entity.P_El_Act_var)

        self.P_El_Act_var.lb = -gurobi.GRB.INFINITY
        P_Th_var_sum = gurobi.quicksum(P_Th_var_list)
        P_El_var_sum = gurobi.quicksum(P_El_var_list)
        model.addConstr(0 == P_Th_var_sum)
        model.addConstr(self.P_El_Act_var == P_El_var_sum)

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        for entity in self.get_lower_entities():
            entity.update_deviation_model(model, timestep, mode)
        p = self.P_El_Schedule[timestep]
        model.setObjective(
            self.P_El_Act_var * self.P_El_Act_var - 2 * p * self.P_El_Act_var
        )

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        super(Building, self).update_actual_schedule(timestep)

        for entity in self.get_lower_entities():
            entity.update_actual_schedule(timestep)

    def _init_deviation_model(self, mode=""):
        model = gurobi.Model(self._long_ID + "_deviation_model")
        model.setParam("OutputFlag", False)
        model.setParam("LogFile", "")
        self.populate_deviation_model(model, mode)
        self.deviation_model = model

    def simulate(self, mode='', debug=True):
        """Simulation of pseudo real behaviour.

        Simulate `self.timer.mpc_step_width` timesteps from current timestep
        on.

        Parameters
        ----------
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        debug : bool, optional
            Specify wether detailed debug information shall be printed.
        """
        if self.deviation_model is None:
            self._init_deviation_model(mode)

        timestep = self.timestep
        for t in range(self.timer.mpc_step_width):
            self.update_deviation_model(self.deviation_model,
                                        t + timestep, mode)
            # minimize deviation from schedule
            obj = gurobi.QuadExpr(
                (self.P_El_Act_var - self.P_El_Schedule[t + timestep])
                *
                (self.P_El_Act_var - self.P_El_Schedule[t + timestep])
            )
            self.deviation_model.setObjective(obj)
            self.deviation_model.optimize()
            if self.deviation_model.status != 2:
                if debug:
                    util.analyze_model(self.deviation_model)
                raise UnoptimalError(
                    "Could not retrieve solution from deviation model."
                )
            self.update_actual_schedule(t + timestep)

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(Building, self).save_ref_schedule()

        for entity in self.get_lower_entities():
            entity.save_ref_schedule()

    def reset(self, schedule=True, actual=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        actual : bool, optional
            Specify if to reset actual schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        super(Building, self).reset(schedule, actual, reference)

        for entity in self.get_lower_entities():
            entity.reset(schedule, actual, reference)

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
        if self.hasBes:
            yield self.bes
        yield from self.apartments
