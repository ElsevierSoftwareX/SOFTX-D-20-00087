import numpy as np
import pyomo.environ as pyomo

import pycity_base.classes.supply.HeatPump as hp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from ..util.generic_constraints import LowerActivationLimit


class HeatPump(ThermalEntity, ElectricalEntity, hp.Heatpump):
    """
    Extension of pyCity_base class Heatpump for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, cop=None,
                 lower_activation_limit=0):
        """Initialize HeatPump.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal thermal power of the heat pump in [kW].
        cop : numpy.ndarray or int or float, optional
            If array, it must provide the coefficient of performance (COP) for
            each time step in the simulation horizon.
            If int or float, a constant COP over the whole horizon is assumed.
            If omitted, an air-water heat pump is assumed and the COP is
            calculated with the ambient air temperature.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the heat pump as a
            percentage of the rated power. When the heat pump is running its
            power nust be zero or between the lower activation limit and its
            rated power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        simu_horizon = environment.timer.simu_horizon
        if cop is None:
            (tAmbient,) = environment.weather.getWeatherForecast(
                getTAmbient=True
            )
            ts = environment.timer.time_in_year()
            tAmbient = tAmbient[ts:ts + simu_horizon]
            # Flow temperature of 55 C (328 K) and eta of 36%
            cop = 0.36 * 328 / (55 - tAmbient)
        elif isinstance(cop, (int, float)):
            cop = np.full(simu_horizon, cop)
        elif not isinstance(cop, np.ndarray):
            raise TypeError(
                "Unknown type for `cop`: {}. Must be `numpy.ndarray`, `int` "
                "or `float`".format(type(cop))
            )
        super().__init__(environment, [], 55, [], [], cop, 55, lower_activation_limit)
        self._long_ID = "HP_" + self._ID_string
        self.COP = cop
        self.P_Th_Nom = P_Th_nom

        self.Activation_constr = LowerActivationLimit(self, "P_Th", lower_activation_limit, -P_Th_nom)

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel.

        Call parent's `populate_model` method and set thermal variables lower
        bounds to `-self.P_Th_Nom` and the upper bounds to zero. Also add
        constraint to bind electrical demand to thermal output.

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

            m.COP = pyomo.Param(m.t, mutable=True)

            def p_coupl_rule(model, t):
                return model.P_Th_vars[t] + model.COP[t] * model.P_El_vars[t] == 0
            m.p_coupl_constr = pyomo.Constraint(m.t, rule=p_coupl_rule)

            self.Activation_constr.apply(m, mode)
        else:
            raise ValueError(
                "Mode %s is not implemented by heat pump." % str(mode)
            )

    def update_model(self, mode=""):
        m = self.model
        cop = self.COP[self.op_slice]
        for t in self.op_time_vec:
            m.COP[t] = cop[t]
