import numpy as np
import pyomo.environ as pyomo
from pyomo.core.expr.numeric_expr import ExpressionBase
import pycity_base.classes.supply.Boiler as bl

from .thermal_entity import ThermalEntity
from ..util.generic_constraints import LowerActivationLimit


class Boiler(ThermalEntity, bl.Boiler):
    """
    Extension of pyCity_base class Boiler for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, eta=1, lower_activation_limit=0):
        """Initialize Boiler.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal heat output in [kW].
        eta : float, optional
            Efficiency.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the boiler as a
            percentage of the rated power. When the boiler is running its
            power must be zero or between the lower activation limit and its
            rated power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        # Flow temperature of 55 C
        super().__init__(environment, 1000*P_Th_nom, eta, 55, lower_activation_limit)
        self._long_ID = "BL_" + self._ID_string
        self.P_Th_Nom = P_Th_nom

        self.Activation_constr = LowerActivationLimit(self, "P_Th", lower_activation_limit, -P_Th_nom)

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method and set variables upper bounds
        to `self.P_Th_Nom`.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control
                           decisions
        """
        super().populate_model(model, mode)
        m = self.model

        if mode == "convex" or "integer":
            m.P_Th_vars.setlb(-self.P_Th_Nom)
            m.P_Th_vars.setub(0)

            self.Activation_constr.apply(m, mode)
        else:
            raise ValueError(
                "Mode %s is not implemented by boiler." % str(mode)
            )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the boiler wheighted with coeff.
        Sum of self.P_Th_vars.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        ExpressionBase :
            Objective function.
        """
        return coeff * pyomo.sum_product(self.model.P_Th_vars)
