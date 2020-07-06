import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.CityDistrict as cd

from .electrical_entity import ElectricalEntity


class CityDistrict(ElectricalEntity, cd.CityDistrict):
    """
    Extension of pyCity_base class CityDistrict for scheduling purposes. Also represents the aggregator.
    """

    def __init__(self, environment, objective='price', valley_profile=None):
        """Initialize CityDistrict.

        Parameters
        ----------
        environment : Environment
        objective : str, optional
            Objective for the aggregator. Defaults to 'price'.
            - 'price' : Optimize for the prices given by `prices.da_prices`.
            - 'peak-shaving' : Try to flatten the scheudle as much as
                               possible.
            - 'max-consumption' : Try to reduce the maximum of the absolute values
                                  of the schedule as much as possible.
            - 'none' : No objective.
        valley_profile : np.ndarray, optional
            Profile to be filled with valley filling.
        """
        super().__init__(environment)
        self._long_ID = "CD_" + self._ID_string
        self.objective = objective
        self.valley_profile = valley_profile

    def populate_model(self, model, mode="convex"):
        """Add city district block to pyomo ConcreteModel.

        Call parent's `populate_model` methods and set variables lower
        bounds to `None`.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        m = self.model

        if mode in ["convex", "integer"]:
            m.P_El_vars.setlb(None)
        else:
            raise ValueError(
                "Mode %s is not implemented by city district." % str(mode)
            )

    def get_objective(self, coeff=1):
        if self.objective == 'valley-filling':
            e = coeff * pyomo.sum_product(self.model.P_El_vars, self.model.P_El_vars)
            valley = self.valley_profile[self.op_slice]
            e += 2 * coeff * pyomo.sum_product(valley, self.model.P_El_vars)
            return e
        elif self.objective == 'price':
            prices = self.environment.prices.da_prices[self.op_slice]
            s = sum(abs(prices))
            if s > 0:
                prices = prices * self.op_horizon / s
                return pyomo.sum_product(prices, self.model.P_El_vars)
            else:
                return 0
        return super().get_objective(coeff)

    def get_lower_entities(self):
        for node in self.nodes.values():
            yield node['entity']
