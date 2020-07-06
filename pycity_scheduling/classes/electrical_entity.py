import numpy as np
import pyomo.environ as pyomo

from .optimization_entity import OptimizationEntity


class ElectricalEntity(OptimizationEntity):
    """
    Base class for all electrical entities derived from OptimizationEntity.

    This class provides functionality common to all electrical entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("P_El")

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel.

        Add variables for the electrical demand / supply of the entity to the
        block.

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
            m.P_El_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)

            if self.objective == "max-consumption":
                m.max_consumption_var = pyomo.Var(domain=pyomo.NonNegativeReals)

                def p_consumption_rule(model, t):
                    return model.max_consumption_var >= m.P_El_vars[t]
                m.P_cons_constr = pyomo.Constraint(m.t, rule=p_consumption_rule)

                def p_generation_rule(model, t):
                    return model.max_consumption_var >= -m.P_El_vars[t]
                m.P_gen_constr = pyomo.Constraint(m.t, rule=p_generation_rule)
        else:
            raise ValueError(
                "Mode %s is not implemented by electric entity." % str(mode)
                )

    def get_objective(self, coeff=1):
        if self.objective == 'peak-shaving':
            return coeff * pyomo.sum_product(self.model.P_El_vars, self.model.P_El_vars)
        if self.objective in ['price', 'co2']:
            if self.objective == 'price':
                prices = self.environment.prices.tou_prices
            else:
                prices = self.environment.prices.co2_prices
            prices = prices[self.op_slice]
            s = sum(abs(prices))
            if s > 0:
                prices = prices * self.op_horizon / s
                return coeff * pyomo.sum_product(prices, self.model.P_El_vars)
            else:
                return 0
        if self.objective == "max-consumption":
            if coeff < 0:
                raise ValueError("Setting a coefficient below zero is not supported for the max-consumption objective")
            return coeff * self.model.max_consumption_var
        return super().get_objective(coeff)
