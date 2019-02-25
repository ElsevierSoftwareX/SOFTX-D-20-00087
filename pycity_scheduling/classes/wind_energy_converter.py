import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.WindEnergyConverter as wec

from .electrical_entity import ElectricalEntity
from pycity_scheduling.constants import CO2_EMISSIONS_WIND


class WindEnergyConverter(ElectricalEntity, wec.WindEnergyConverter):
    """
    Extension of pycity class WindEnergyConverter for scheduling purposes.
    """

    def __init__(self, environment, velocity, power,
                 hub_height=70, roughness=0.1, force_renewables=True):
        """Initialize WindEnergyConverter.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        velocity : array_like (numpy.ndarray)
            Wind speeds in [m/s].
        power : array_like (numpy.ndarray)
            Power for given velocities in [kW].
        hub_height : float, optional
            Height of the wind energy converter in [m].
        roughness : float, optional
            Roughness of landscape in [m].
        force_renewables : bool, optional
            `True` if generation may not be reduced for optimization puposes.
        """
        super(WindEnergyConverter, self).__init__(
            environment.timer, environment,
            velocity, power, hub_height, roughness
        )
        self._long_ID = "WEC_" + self._ID_string

        self.force_renewables = force_renewables

        self.objective = None
        wheather_forecast = self.environment.weather.getWeatherForecast
        (full_wind,) = wheather_forecast(getVWind=True)
        ts = self.timer.time_in_year("timesteps", True)
        total_wind = full_wind[ts:ts+self.simu_horizon]
        log_wind = self._logWindProfile(total_wind)
        self.P_El_Supply = np.interp(log_wind, self.velocity,
                                     self.power, right=0)

    def update_model(self, model, mode=""):
        timestep = self.timer.currentTimestep
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
            t1 = self.timer.currentTimestep
            t2 = t1 + self.op_horizon
            obj.addTerms(
                - 2 * coeff * self.P_El_Supply[t1:t2],
                self.P_El_vars
            )
        return obj

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the entity.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        if reference:
            p = self.P_El_Ref_Schedule
        else:
            p = self.P_El_Schedule
        co2 = super(WindEnergyConverter, self).calculate_co2(timestep,
                                                             co2_emissions,
                                                             reference)
        co2 -= sum(p) * self.time_slot * CO2_EMISSIONS_WIND
        return co2
