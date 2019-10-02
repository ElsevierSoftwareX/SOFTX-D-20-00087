import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.PV as pv

from .electrical_entity import ElectricalEntity


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
        super().__init__(environment, area, eta, temperature_nominal, alpha, beta, gamma, tau_alpha)
        self._long_ID = "PV_" + self._ID_string

        self.force_renewables = force_renewables
        self.getPower(currentValues=False)
        ts = self.timer.time_in_year(from_init=True)
        self.P_El_Supply = self.totalPower[ts:ts+self.simu_horizon] / 1000

    def update_model(self, model, mode=""):
        timestep = self.timestep
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
            obj.addTerms(
                - 2*coeff*self.P_El_Supply[self.op_slice],
                self.P_El_vars
            )
        return obj

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        self.P_El_Act_var.lb = -self.P_El_Supply[timestep]
        if mode == 'full' and not self.force_renewables:
            self.P_El_Act_var.ub = 0
        else:
            self.P_El_Act_var.ub = -self.P_El_Supply[timestep]

    def simulate(self, mode='', debug=True):
        """Simulation of pseudo real behaviour.

        Simulate `self.timer.mpc_step_width` timesteps from current timestep
        on.

        Parameters
        ----------
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        debug : bool, optional
            Specify wether detailed debug information shall be printed.
        """
        op_slice = self.op_slice
        if self.force_renewables:
            p = self.P_El_Supply
        else:
            p = np.minimum(self.P_El_Supply, self.P_El_Schedule)
        np.copyto(self.P_El_Act_Schedule[op_slice], p[op_slice])
