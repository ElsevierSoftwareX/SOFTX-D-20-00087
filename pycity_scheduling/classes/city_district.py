import numpy as np
import gurobipy as gurobi
import pycity_base.classes.CityDistrict as cd

from .electrical_entity import ElectricalEntity
from pycity_scheduling import constants, classes, util


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

    def calculate_costs(self, timestep=None, prices=None, reference=False,
                        feedin_factor=None):
        """Calculate electricity costs for the CityDistrict.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
        reference : bool, optional
            `True` if costs for reference schedule.
        feedin_factor : float, optional
            Factor which is multiplied to the prices for feed-in revenue.

        Returns
        -------
        float :
            Electricity costs in [ct].
        """
        if prices is None:
            prices = self.environment.prices.da_prices
        if feedin_factor is None:
            feedin_factor = 1
        costs = ElectricalEntity.calculate_costs(self, timestep, prices,
                                                 reference, feedin_factor)
        return costs

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the CityDistrict.

        The CO2 emissions are made up of two parts: the emissions for the
        imported energy and the emissions of the local generation.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            Specific CO2 emissions for the imported energy over all timesteps
            in the simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        p = util.get_schedule(self, reference, timestep)
        if co2_emissions is None:
            co2_emissions = self.environment.prices.co2_prices
        if timestep:
            co2_emissions = co2_emissions[:timestep]
        bat_schedule = sum(
            util.get_schedule(e, reference, timestep)
            for e in classes.filter_entities(self, 'BAT')
        )
        p = p - bat_schedule
        co2 = self.time_slot * np.dot(p[p>0], co2_emissions[p>0])

        chp_schedule = sum(
            util.get_schedule(e, reference, timestep, thermal=True).sum()
            * (1+e.sigma) / e.omega
            for e in classes.filter_entities(self, 'CHP')
        )
        pv_schedule = sum(
            util.get_schedule(e, reference, timestep).sum()
            for e in classes.filter_entities(self, 'PV')
        )
        wec_schedule = sum(
            util.get_schedule(e, reference, timestep).sum()
            for e in classes.filter_entities(self, 'WEC')
        )
        co2 -= chp_schedule * self.time_slot * constants.CO2_EMISSIONS_GAS
        co2 -= pv_schedule * self.time_slot * constants.CO2_EMISSIONS_PV
        co2 -= wec_schedule * self.time_slot * constants.CO2_EMISSIONS_WIND

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
