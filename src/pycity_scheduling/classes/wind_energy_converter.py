"""
The pycity_scheduling Framework


Institution:
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.wind_energy_converter as wec

from pycity_scheduling.classes.electrical_entity import ElectricalEntity


class WindEnergyConverter(ElectricalEntity, wec.WindEnergyConverter):
    """
    Extension of pyCity_base class WindEnergyConverter for scheduling purposes.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    velocity : numpy.ndarray
        Wind speeds in [m/s].
    power : numpy.ndarray
        Power for given velocities in [kW].
    hub_height : float, optional
        Height of the wind energy converter in [m].
    roughness : float, optional
        Roughness of landscape in [m].
    force_renewables : bool, optional
        `True` if generation may not be reduced for optimization purposes.


    Notes
    -----
    - The following constraint is added for removing the bounds from EE:

    .. math::
        p_{el} &=& -p_{el\\_supply}, & \\quad \\text{if force_renewables} \\\\
        0 \\geq p_{el} &\\geq& -p_{el\\_supply} , & \\quad \\text{else}
    """

    def __init__(self, environment, velocity, power,
                 hub_height=70, roughness=0.1, force_renewables=True):
        super(WindEnergyConverter, self).__init__(environment, velocity, power, hub_height, roughness)
        self._long_id = "WEC_" + self._id_string

        self.force_renewables = force_renewables
        self.p_el_supply = self._get_power_supply()

    def _get_power_supply(self):
        # Base class cannot compute values for the whole simulation horizon
        wheather_forecast = self.environment.weather.getWeatherForecast
        (full_wind,) = wheather_forecast(getVWind=True)
        ts = self.timer.time_in_year(from_init=True)
        total_wind = full_wind[ts:ts + self.simu_horizon]
        log_wind = self._logWindProfile(total_wind)
        return np.interp(log_wind, self.velocity, self.power, right=0)

    def populate_model(self, model, mode="convex"):
        super().populate_model(model, mode)
        return

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        for t in self.op_time_vec:
            m.p_el_vars[t].setlb(-self.p_el_supply[timestep + t])
            if self.force_renewables:
                m.p_el_vars[t].setub(-self.p_el_supply[timestep + t])
            else:
                m.p_el_vars[t].setub(0.0)
        return

    def get_objective(self, coeff=1):
        """
        Objective function of the WindEnergyConverter.

        Return the objective function of the wind energy converter weighted
        with `coeff`. Depending on `self.force_renewables` leave objective
        function empty or build quadratic objective function to minimize
        discrepancy between available power and produced power.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        ExpressionBase :
            Objective function.
        """
        m = self.model

        s = pyomo.sum_product(m.p_el_vars, m.p_el_vars)
        s += -2 * pyomo.sum_product(self.p_el_supply[self.op_slice], m.p_el_vars)
        return coeff * s
