import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.HeatPump as hp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class HeatPump(ThermalEntity, ElectricalEntity, hp.Heatpump):
    """
    Extension of pycity class Heatpump for scheduling purposes.
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

        self.coupl_constrs = []
        self.Act_coupl_constr = None

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model.

        Call parent's `populate_model` method and set thermal variables lower
        bounds to `-self.P_Th_Nom` and the upper bounds to zero. Also add
        constraint to bind electrical demand to thermal output.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)

        if mode == "convex" or "integer":
            for var in self.P_Th_vars:
                var.lb = -self.P_Th_Nom
                var.ub = 0
            for t in self.op_time_vec:
                self.coupl_constrs.append(model.addConstr(
                    self.P_El_vars[t] - self.P_Th_vars[t] == 0,
                    "{0:s}_Th_El_coupl_at_t={1}".format(self._long_ID, t)
                ))
            if mode == "integer" and self.lowerActivationLimit != 0.0:
                # Add additional binary variables representing operating state
                for t in self.op_time_vec:
                    self.P_State_vars.append(
                        model.addVar(
                            vtype=gurobi.GRB.BINARY,
                            name="%s_Mode_at_t=%i"
                                 % (self._long_ID, t + 1)
                        )
                    )
                model.update()

                for t in self.op_time_vec:
                    # Couple state to operating variable
                    model.addConstr(
                        self.P_Th_vars[t][t]
                        >= -self.P_State_vars[t] * self.P_Th_Nom
                    )
                    model.addConstr(
                        self.P_Th_vars[t][t]
                        <= -self.P_State_vars[t] * self.P_Th_Nom * self.lowerActivationLimit
                    )
                    # Remove redundant limits of P_Th_vars
                    self.P_Th_vars[t].lb = -gurobi.GRB.INFINITY
                    self.P_Th_vars[t].ub = gurobi.GRB.INFINITY
        else:
            raise ValueError(
                "Mode %s is not implemented by heat pump." % str(mode)
            )

    def update_model(self, model, mode=""):
        for t in self.op_time_vec:
            cop = self.COP[t+self.timestep]
            model.chgCoeff(self.coupl_constrs[t], self.P_El_vars[t], cop)

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds variables, sets the correct bounds to the thermal variable and
        adds a coupling constraint.
        """
        super().populate_deviation_model(model, mode)

        self.P_Th_Act_var.lb = -self.P_Th_Nom
        self.P_Th_Act_var.ub = 0
        self.Act_coupl_constr = model.addConstr(
            self.P_El_Act_var + self.P_Th_Act_var == 0
        )

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep.

        Changes the coefficient of the coupling constraint to the current COP.
        """
        model.chgCoeff(self.Act_coupl_constr,
                       self.P_El_Act_var, self.COP[timestep])
