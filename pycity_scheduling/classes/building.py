import numpy as np
import gurobipy as gurobi
import pycity_base.classes.Building as bd

from .electrical_entity import ElectricalEntity
from ..exception import PyCitySchedulingInitError


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
        super(Building, self).__init__(environment.timer, environment)

        self._long_ID = "BD_" + self._ID_string
        if name is None:
            self.name = self._long_ID
        else:
            self.name = name

        self.objective = objective
        self.profile_type = profile_type
        self.building_type = building_type
        self.storage_end_equality = storage_end_equality

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
            raise PyCitySchedulingInitError(
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
        timestep = self.timer.currentTimestep
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
            prices = prices[timestep:timestep+self.op_horizon]
            prices = prices * self.op_horizon / sum(prices)
            obj.addTerms(
                coeff * prices,
                self.P_El_vars
            )
        return obj

    def update_model(self, model, mode=""):
        for entity in self.get_lower_entities():
            entity.update_model(model, mode)

    def update_schedule(self, mode=""):
        super(Building, self).update_schedule(mode)
        for entity in self.get_lower_entities():
            entity.update_schedule()

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(Building, self).save_ref_schedule()

        for entity in self.get_lower_entities():
            entity.save_ref_schedule()

    def reset(self, schedule=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        super(Building, self).reset(schedule, reference)

        for entity in self.get_lower_entities():
            entity.reset(schedule, reference)

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the Building.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        co2 = 0
        for entity in self.get_lower_entities():
            co2 += entity.calculate_co2(timestep, reference)
        return co2

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
        if self.hasBes:
            yield self.bes
        yield from self.apartments

    def compute_flexibility(self):
        if self.bes.hasTes:
            return self.bes.tes.compute_flexibility()
        else:
            return 0, 0, 0, 0
