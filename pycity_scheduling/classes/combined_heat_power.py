import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.CHP as chp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from ..util.generic_constraints import LowerActivationLimit


class CombinedHeatPower(ThermalEntity, ElectricalEntity, chp.CHP):
    """
    Extension of pyCity_base class CHP for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, P_El_nom=None, eta=1,
                 lower_activation_limit=0):
        """Initialize CombinedHeatPower.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal thermal power output in [kW].
        P_El_nom : float, optional
            Nominal electrical power output in [kW]. Defaults to `P_Th_nom`.
        eta : float, optional
            Total efficiency of the CHP.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the CHP as a
            percentage of the rated power. When the CHP is running its power
            must be zero or between the lower activation limit and its rated
            power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        q_nominal = P_Th_nom * 1000
        if P_El_nom is None:
            p_nominal = q_nominal
        else:
            p_nominal = P_El_nom * 1000
        # Flow temperature of 55 C
        super().__init__(environment, p_nominal, q_nominal, eta, 55, lower_activation_limit)
        self._long_ID = "CHP_" + self._ID_string
        self.P_Th_Nom = P_Th_nom
        self.Activation_constr = LowerActivationLimit(self, "P_Th", lower_activation_limit, -P_Th_nom)

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel.

        Call both parents' `populate_model` methods and set the upper bounds
        of the thermal variables to `self.P_Th_Nom`, the lower bounds of the
        electrical variables to `-self.P_El_Nom` and the upper bounds to zero.
        Also add constraints to bind electrical demand to thermal output.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)
        m = self.model

        if mode in ["convex", "integer"]:
            m.P_Th_vars.setlb(-self.P_Th_Nom)
            m.P_Th_vars.setub(0)
            m.P_El_vars.setlb(-self.P_Th_Nom)
            m.P_El_vars.setub(0)

        # original function
        # 'qubic' -> would not work with Gurobi
        # COP = [
        #     -0.2434*(self.P_Th_vars[t]/self.P_Th_Nom)**2
        #     +1.1856*(self.P_Th_vars[t]/self.P_Th_Nom)
        #     +0.0487
        #     for t in self.op_time_vec
        # ]
        # function linearised with quadratic regression over the interval
        # [0, 1]
        # COP = [
        #     0.9422 * self.P_Th_vars[t] * (1 / self.P_Th_Nom) + 0.0889
        #     for t in self.op_time_vec
        #     ]

            def p_coupl_rule(model, t):
                return model.P_Th_vars[t] * self.sigma == model.P_El_vars[t]
            m.P_coupl_constr = pyomo.Constraint(m.t, rule=p_coupl_rule)

            self.Activation_constr.apply(m, mode)
        else:
            raise ValueError(
                "Mode %s is not implemented by CHP." % str(mode)
            )
