import gurobipy as gurobi
import pycity_base.classes.CityDistrict as cd

from .electrical_entity import ElectricalEntity


class CityDistrict(ElectricalEntity, cd.CityDistrict):
    """
    Extension of pyCity class CityDistrict for scheduling purposes. Also works
    as the aggregator.
    """

    def __init__(self, environment, objective="price"):
        """Initialize CityDistrict.

        Parameters
        ----------
        environment : Environment
        objective : str, optional
            Objective for the aggregator. Defaults to 'price'.
            - 'price' : Optimize for the prices given by `prices.da_prices`.
            - 'valley_filling' : Try to flatten the scheudle as much as
                                 possible.
            - 'none' : No objective.
        """
        super(CityDistrict, self).__init__(environment.timer, environment)
        self._long_ID = "CD_" + self._ID_string

        self.objective = objective

    def populate_model(self, model, mode=""):
        super(CityDistrict, self).populate_model(model, mode)

        for var in self.P_El_vars:
            var.lb = -gurobi.GRB.INFINITY

    def get_objective(self, coeff=1):
        obj = gurobi.QuadExpr()
        if self.objective == "valley_filling":
            obj.addTerms(
                [1] * self.op_horizon,
                self.P_El_vars,
                self.P_El_vars
            )
        elif self.objective == "price":
            time_shift = self.timer.currentTimestep
            prices = self.environment.prices.da_prices
            obj.addTerms(
                prices[time_shift:time_shift+self.op_horizon],
                self.P_El_vars
            )
        return obj

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(CityDistrict, self).save_ref_schedule()

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
        super(CityDistrict, self).reset(schedule, reference)
        for entity in self.get_lower_entities():
            entity.reset(schedule, reference)

    def calculate_costs(self, timestep=None, prices=None, reference=False):
        """Calculate electricity costs for the CityDistrict.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
        reference : bool, optional
            `True` if costs for reference schedule.

        Returns
        -------
        float :
            Electricity costs in [ct].
        """
        if prices is None:
            prices = self.environment.prices.da_prices
        costs = ElectricalEntity.calculate_costs(self, timestep,
                                                 prices, reference)
        return costs

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the CityDistrict.

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
        co2 = sum(
            e.calculate_co2(timestep, reference)
            for e in self.get_lower_entities()
        )
        return co2

    def compute_flexibility(self):
        """Return flexibility metrics.

        Return the flexibility metrics of the first building found, assuming
        that only one Building is present in the district.

        Returns
        -------
        float :
            Flexibility in [kWh].
        float :
            Relative flexibility.
        float :
            Residual flexibility in [kWh].
        float :
            Relative residual flexibility.

        Notes
        -----
         - Exploits the actual function of CityDistrict (aggregation of many
           entities) to compute metrics for only one Building.
        """
        for entity in self.get_lower_entities():
            if entity._kind == "building":
                return entity.compute_flexibility()

    def get_lower_entities(self):
        for node in self.nodes.values():
            yield node['entity']
