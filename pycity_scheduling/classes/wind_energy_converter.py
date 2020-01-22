import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.WindEnergyConverter as wec

from .electrical_entity import ElectricalEntity


class WindEnergyConverter(ElectricalEntity, wec.WindEnergyConverter):
    """
    Extension of pyCity_base class WindEnergyConverter for scheduling purposes.
    """

    def __init__(self, environment, velocity, power,
                 hub_height=70, roughness=0.1, force_renewables=True):
        """Initialize WindEnergyConverter.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        velocity : numpy.ndarray
            Wind speeds in [m/s].
        power : anumpy.ndarray
            Power for given velocities in [kW].
        hub_height : float, optional
            Height of the wind energy converter in [m].
        roughness : float, optional
            Roughness of landscape in [m].
        force_renewables : bool, optional
            `True` if generation may not be reduced for optimization puposes.
        """
        super(WindEnergyConverter, self).__init__(environment, velocity, power,
                                                  hub_height, roughness)
        self._long_ID = "WEC_" + self._ID_string

        self.force_renewables = force_renewables
        self.P_El_Supply = self._get_power_supply()

    def _get_power_supply(self):
        # Base class cannot compute values for the whole simulation horizon
        wheather_forecast = self.environment.weather.getWeatherForecast
        (full_wind,) = wheather_forecast(getVWind=True)
        ts = self.timer.time_in_year(from_init=True)
        total_wind = full_wind[ts:ts + self.simu_horizon]
        log_wind = self._logWindProfile(total_wind)
        return np.interp(log_wind, self.velocity, self.power, right=0)

    def update_model(self, model, mode=""):
        timestep = self.timestep
        for t in self.op_time_vec:
            self.P_El_vars[t].lb = -self.P_El_Supply[t+timestep]
            if self.force_renewables:
                self.P_El_vars[t].ub = -self.P_El_Supply[t+timestep]
            else:
                self.P_El_vars[t].ub = 0

    def get_objective(self, coeff=1):
        """Objective function of the WindEnergyConverter.

        Return the objective function of the wind energy converter wheighted
        with `coeff`. Depending on `self.force_renewables` leave objective
        function empty or build quadratic objective function to minimize
        discrepancy between available power and produced power.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        obj = gurobi.QuadExpr()
        if not self.force_renewables:
            obj.addTerms(
                [coeff] * self.op_horizon,
                self.P_El_vars,
                self.P_El_vars
            )
            obj.addTerms(
                - 2 * coeff * self.P_El_Supply[self.op_slice],
                self.P_El_vars
            )
        return obj

    def simulate(self):
        op_slice = self.op_slice
        if self.force_renewables:
            p = self.P_El_Supply
        else:
            p = np.minimum(self.P_El_Supply, self.P_El_Schedule)
        np.copyto(self.P_El_Act_Schedule[op_slice], p[op_slice])

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        self.P_El_Act_var.lb = -self.P_El_Supply[timestep]
        if mode == 'full' and not self.force_renewables:
            self.P_El_Act_var.ub = 0
        else:
            self.P_El_Act_var.ub = -self.P_El_Supply[timestep]
