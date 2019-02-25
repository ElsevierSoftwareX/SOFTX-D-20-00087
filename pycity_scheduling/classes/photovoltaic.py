import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.PV as pv

from .electrical_entity import ElectricalEntity
from pycity_scheduling.constants import CO2_EMISSIONS_PV


class Photovoltaic(ElectricalEntity, pv.PV):
    """
    Extension of pycity class PV for scheduling purposes.
    """

    def __init__(self, environment, area, eta, temperature_nominal=45,
                 alpha=0, beta=0, gamma=0, tau_alpha=0.9,
                 force_renewables=True):
        """Initialize Photovoltaic.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        area : float
            Installation area in [m^2].
        eta : float
            Electrical efficiency at NOCT conditions.
        temperature_nominal : float
            Nominal cell temperature at NOCT conditions in [°C].
        alpha : float
            Temperature coefficient at NOCT conditions.
        beta : float, optional
            Slope, the angle (in degree) between the plane of the surface in
            question and the horizontal. 0 <= beta <= 180. If beta > 90, the
            surface faces downwards.
        gamma : float, optional
            Surface azimuth angle. The deviation of the projection on a
            horizontal plane of the normal to the surface from the local
            meridian, with zero due south, east negative, and west positive.
            -180 <= gamma <= 180
        tau_alpha : float
            Optical properties of the PV unit. Product of absorption and
            transmission coeffients.
            According to Duffie, Beckman - Solar Engineering of Thermal
            Processes (4th ed.), page 758, this value is typically close to
            0.9.
        force_renewables : bool, optional
            `True` if generation may not be reduced for optimization puposes.
        """
        super(Photovoltaic, self).__init__(environment.timer, environment,
                                           area, eta, temperature_nominal,
                                           alpha, beta, gamma, tau_alpha)
        self._long_ID = "PV_" + self._ID_string

        self.force_renewables = force_renewables

        power, radiation = self._computePower()
        ts = self.timer.time_in_year("timesteps", True)
        self.totalPower = power[ts:ts+self.simu_horizon]
        self.totalRadiation = radiation[ts:ts+self.simu_horizon]
        self.P_El_Supply = self.totalPower/1000

    def update_model(self, model, mode=""):
        timestep = self.timer.currentTimestep
        for t in self.op_time_vec:
            self.P_El_vars[t].lb = -self.P_El_Supply[t+timestep]
            if self.force_renewables:
                self.P_El_vars[t].ub = -self.P_El_Supply[t+timestep]
            else:
                self.P_El_vars[t].ub = 0

    def get_objective(self, coeff=1):
        """Objective function of the Photovoltaic.

        Return the objective function of the photovoltaic wheighted
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
                [coeff]*self.op_horizon,
                self.P_El_vars,
                self.P_El_vars
            )
            t1 = self.timer.currentTimestep
            t2 = t1+self.op_horizon
            obj.addTerms(
                - 2*coeff*self.P_El_Supply[t1:t2],
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
        co2 = super(Photovoltaic, self).calculate_co2(timestep, co2_emissions,
                                                      reference)
        co2 -= sum(p) * self.time_slot * CO2_EMISSIONS_PV
        return co2
