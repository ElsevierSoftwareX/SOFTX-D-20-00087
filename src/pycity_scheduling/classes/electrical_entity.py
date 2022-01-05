"""
The pycity_scheduling framework


Copyright (C) 2022,
Institute for Automation of Complex Power Systems (ACS),
E.ON Energy Research Center (E.ON ERC),
RWTH Aachen University

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.classes.optimization_entity import OptimizationEntity


class ElectricalEntity(OptimizationEntity):
    """
    Base class for all electrical entities derived from OptimizationEntity.

    This class provides functionality common to all electrical entities.
    It adds variables for the electrical demand / supply of the entity to the
    block.

    Parameters
    ----------
    model : pyomo.ConcreteModel
    mode : str, optional
        Specifies which set of constraints to use.

        - `convex`  : Use linear constraints
        - `integer`  : Use same constraints as convex mode

    Notes
    -----
    - EEs add the :math:`p_{el}` variable to the model. When not modified
      by other classes, the following constraint is added:

    .. math::
        p_{el} \\geq 0
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("p_el")

    def populate_model(self, model, mode="convex"):
        super().populate_model(model, mode)
        m = self.model

        if mode in ["convex", "integer"]:
            m.p_el_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)

            if self.objective == "max-consumption":
                m.max_consumption_var = pyomo.Var(domain=pyomo.Reals, bounds=(0, None), initialize=0)

                def p_consumption_rule(model, t):
                    return model.max_consumption_var >= m.p_el_vars[t]
                m.p_cons_constr = pyomo.Constraint(m.t, rule=p_consumption_rule)

                def p_generation_rule(model, t):
                    return model.max_consumption_var >= -m.p_el_vars[t]
                m.p_gen_constr = pyomo.Constraint(m.t, rule=p_generation_rule)

            if self.objective == "self-consumption":
                m.p_export_var = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)
                m.p_import_var = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)

                def p_self_consumption_rule(model, t):
                    return model.p_import_var[t] - model.p_export_var[t] == m.p_el_vars[t]
                m.p_self_cons_constr = pyomo.Constraint(m.t, rule=p_self_consumption_rule)

            if self.objective == "flexibility-quantification":
                m.max_p_flex_var = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)

                def max_p_flex_consumption_rule(model, t):
                    return model.max_p_flex_var[t] >= m.p_el_vars[t]
                m.max_p_flex_cons_constr = pyomo.Constraint(m.t, rule=max_p_flex_consumption_rule)

                def max_p_flex_generation_rule(model, t):
                    return model.max_p_flex_var[t] >= -m.p_el_vars[t]
                m.max_p_flex_gen_constr = pyomo.Constraint(m.t, rule=max_p_flex_generation_rule)
        else:
            raise ValueError("Mode %s is not implemented by electrical entity." % str(mode))
        return

    def get_objective(self, coeff=1):
        if self.objective == 'peak-shaving':
            return coeff * pyomo.sum_product(self.model.p_el_vars, self.model.p_el_vars)
        if self.objective in ['price', 'co2']:
            if self.objective == 'price':
                prices = self.environment.prices.tou_prices
            else:
                prices = self.environment.prices.co2_prices
            prices = prices[self.op_slice]
            s = sum(abs(prices))
            if s > 0:
                prices = prices * self.op_horizon / s
                return coeff * pyomo.sum_product(prices, self.model.p_el_vars)
            else:
                return 0
        if self.objective == "max-consumption":
            if not hasattr(self.model, "max_consumption_var"):
                raise ValueError("Objective 'max-consumption' needs to be selected during populate_model call.")
            if coeff < 0:
                raise ValueError("Setting a coefficient below zero is not supported for the max-consumption objective.")
            return coeff * self.model.max_consumption_var
        if self.objective == "self-consumption":
            if not hasattr(self.model, "p_export_var"):
                raise ValueError("'Objective self-consumption' needs to be selected during populate_model call.")
            if coeff < 0:
                raise ValueError("Setting a coefficient below zero is not supported for the self-consumption "
                                 "objective.")
            return coeff * pyomo.sum_product(self.model.p_export_var, self.model.p_export_var)
        if self.objective == 'flexibility-quantification':
            if not hasattr(self.model, "max_p_flex_var"):
                raise ValueError("Objective 'flexibility-quantification' needs to be selected during populate_model "
                                 "call.")
            return coeff * pyomo.sum_product(self.model.max_p_flex_var, self.model.max_p_flex_var)
        return super().get_objective(coeff)
