import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.classes.optimization_entity import OptimizationEntity

class Constraint:
    """
    Base class for all generic constraints.

    This class provides functionality common to all generic constraints.
    Generic constraints can be easily added to an entity block.
    """
    def apply(self, model):
        """
        Apply constraint to block during populate_model method call.

        Parameters
        ----------
        model : pyomo.Block
            The block corresponding to the entity the constraint should
            be applied to.
        """
        raise NotImplementedError()

class LowerActivationLimit(Constraint):
    """
    Constraint Class for adding lower activation limits

    This class provides functionality to add lower activation limits
    to entities. Adds no new constraints and variables if not in integer
    mode or if not required. A new state schedule is also created for
    the entity.
    """
    def __init__(self, o, var_name, lower_activation_limit, var_nom):
        """
        Initialize Constraint for a specific entity and create the new
        state schedule.


        Parameters
        ----------
        o : OptimizationEntity
            The entity to add the constraint to.
        var_name : str
            The variable name the constraint should be applied to.
        lower_activation_limit : float (0 <= lowerActivationLimit <= 1)
            Defines the lower activation limit. For example, heat pumps
            are typically able to operate between 50% part load and rated
            load. In this case, lowerActivationLimit would be 0.5
            Two special cases:
            Linear behaviour: lowerActivationLimit = 0.0
            Two-point controlled: lowerActivationLimit = 1.0
        var_nom : float
            The maximum or minimum value the variable has when operating
            under maximum load.
        """
        self.var_nom = var_nom
        self.var_name = var_name
        self.lowerActivationLimit = lower_activation_limit
        o.new_var(var_name+"_State", dtype=np.bool, func=lambda model, t: abs(getattr(model, self.var_name + "_vars")
                                                                              [t].value) > abs(0.01 * var_nom))

    def apply(self, m, mode):
        if mode == "integer" and self.lowerActivationLimit != 0.0 and self.var_nom != 0.0:
            # Add additional binary variables representing operating state
            if hasattr(m, self.var_name+"_State"):
                raise ValueError("model already has a component named: {}". format(self.var_name+"_State"))

            var = pyomo.Var(m.t, domain=pyomo.Binary)
            m.add_component(self.var_name+"_State_vars", var)

            # Couple state to operating variable
            orig_var = getattr(m, self.var_name + "_vars")
            def p_state_rule(model, t):
                orig_var = getattr(m, self.var_name + "_vars")
                var = getattr(m, self.var_name + "_State_vars")
                if self.var_nom > 0:
                    return orig_var[t] <= var[t] * self.var_nom
                else:
                    return orig_var[t] >= var[t] * self.var_nom

            if hasattr(m, self.var_name+"_State_constr"):
                raise ValueError("model already has a component named: {}". format(self.var_name+"_State_constr"))
            m.add_component(self.var_name+"_State_constr", pyomo.Constraint(m.t, rule=p_state_rule))

            def p_activation_rule(model, t):
                orig_var = getattr(m, self.var_name + "_vars")
                var = getattr(m, self.var_name + "_State_vars")
                if self.var_nom > 0:
                    return orig_var[t] >= var[t] * self.var_nom * self.lowerActivationLimit
                else:
                    return orig_var[t] <= var[t] * self.var_nom * self.lowerActivationLimit

            if hasattr(m, self.var_name+"_Activation_constr"):
                raise ValueError("model already has a component named: {}". format(self.var_name+"_Activation_constr"))
            m.add_component(self.var_name+"_Activation_constr", pyomo.Constraint(m.t, rule=p_activation_rule))

            # Remove redundant limits of P_Th_vars
            orig_var.setlb(None)
            orig_var.setub(None)
