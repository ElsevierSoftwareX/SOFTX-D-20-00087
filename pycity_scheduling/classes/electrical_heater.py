import numpy as np
import pyomo.environ as pyomo

import pycity_base.classes.supply.ElectricalHeater as eh
from ..util.generic_constraints import LowerActivationLimit

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class ElectricalHeater(ThermalEntity, ElectricalEntity, eh.ElectricalHeater):
    """
    Extension of pyCity_base class ElectricalHeater for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, eta=1, lower_activation_limit=0):
        """Initialize ElectricalHeater.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal thermal power output in [kW].
        eta : float, optional
            Efficiency of the electrical heater.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the electrical heater
            as a percentage of the rated power. When the electrical heater is
            running its power nust be zero or between the lower activation
            limit and its rated power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        # Flow temperature of 55 C
        super().__init__(environment, P_Th_nom*1000, eta, 55, lower_activation_limit)
        self._long_ID = "EH_" + self._ID_string
        self.P_Th_Nom = P_Th_nom
        self.Activation_constr = LowerActivationLimit(self, "P_Th", lower_activation_limit, -P_Th_nom)

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel.

        Call parent's `populate_model` method and set thermal variables upper
        bounds to `self.P_Th_Nom`. Also add constraint to bind electrical
        demand to thermal output.

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

        if mode == "convex" or "integer":
            m.P_Th_vars.setlb(-self.P_Th_Nom)
            m.P_Th_vars.setub(0)

            def p_coupl_rule(model, t):
                return - model.P_Th_vars[t] == self.eta * model.P_El_vars[t]
            m.p_coupl_constr = pyomo.Constraint(m.t, rule=p_coupl_rule)

            self.Activation_constr.apply(m, mode)

        else:
            raise ValueError(
                "Mode %s is not implemented by electrical heater." % str(mode)
            )
