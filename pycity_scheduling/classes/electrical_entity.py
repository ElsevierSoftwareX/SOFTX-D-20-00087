import numpy as np
import gurobipy as gurobi

from .optimization_entity import OptimizationEntity


class ElectricalEntity(OptimizationEntity):
    """
    Base class for all electrical entities derived from OptimizationEntity.

    This class provides functionality common to all electrical entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("P_El")
        self.max_consumption_var = None

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model.

        Add variables for the electrical demand / supply of the entity to the
        optimization model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        if mode in ["convex", "integer"]:
            for t in self.op_time_vec:
                self.P_El_vars.append(
                    model.addVar(
                        name="%s_P_El_at_t=%i" % (self._long_ID, t+1)
                    )
                )
            self.max_consumption_var = None
            if self.objective == "max-consumption":
                self.max_consumption_var = model.addVar(
                            name="%s_P_El_max" % self._long_ID
                        )
                for t in self.op_time_vec:
                    model.addConstr(
                        self.max_consumption_var >= self.P_El_vars[t]
                    )
                    model.addConstr(
                        self.max_consumption_var >= -self.P_El_vars[t]
                    )
                model.update()
        else:
            raise ValueError(
                "Mode %s is not implemented by electric entity." % str(mode)
                )

    def get_objective(self, coeff=1):
        if self.objective == 'peak-shaving':
            obj = gurobi.QuadExpr()
            obj.addTerms(
                [coeff] * self.op_horizon,
                self.P_El_vars,
                self.P_El_vars
            )
            return obj
        if self.objective in ['price', 'co2']:
            obj = gurobi.LinExpr()
            if self.objective == 'price':
                prices = self.environment.prices.tou_prices
            else:
                prices = self.environment.prices.co2_prices
            prices = prices[self.op_slice]
            s = sum(abs(prices))
            if s > 0:
                prices = prices * self.op_horizon / s
                obj.addTerms(
                    coeff * prices,
                    self.P_El_vars
                )
            return obj
        if self.objective == "max-consumption":
            if coeff < 0:
                raise ValueError("Setting a coefficient below zero is not supported for the max-consumption objective")
            obj = gurobi.LinExpr()
            obj.add(self.max_consumption_var, coeff)
            return obj
        return super().get_objective(coeff)
