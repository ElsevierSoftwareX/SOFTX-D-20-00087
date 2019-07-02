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
            timestep = self.timer.currentTimestep
            prices = self.environment.prices.da_prices
            obj.addTerms(
                prices[timestep:timestep+self.op_horizon],
                self.P_El_vars
            )
        return obj

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(CityDistrict, self).save_ref_schedule()

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
        super(CityDistrict, self).reset(schedule, actual, reference)
        for entity in self.get_lower_entities():
            entity.reset(reference)

    def calculate_costs(self, schedule=None, timestep=None, prices=None,
                        feedin_factor=None):
        """Calculate electricity costs for the CityDistrict.

        Parameters
        ----------
        schedule : str, optional
            Specify which schedule to use.
            `None` : Normal schedule
            'act', 'actual' : Actual schedule
            'ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
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
        costs = ElectricalEntity.calculate_costs(self, schedule, timestep,
                                                 prices, feedin_factor)
        return costs

    def calculate_adj_costs(self, timestep=None, prices=None,
                            total_adjustments=True):
        """Calculate costs for adjustments.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Adjustment prices for simulation horizon.
        total_adjustments : bool, optional
            `True` if positive and negative deviations shall be considered.
            `False` if only positive deviations shall be considered.

        Returns
        -------
        float :
            Adjustment costs in [ct].
        """
        if prices is None:
            prices = self.environment.prices.da_prices
        costs = self.calculate_adj_costs(timestep, prices, total_adjustments)
        return costs

    def get_lower_entities(self):
        for node in self.nodes.values():
            yield node['entity']
