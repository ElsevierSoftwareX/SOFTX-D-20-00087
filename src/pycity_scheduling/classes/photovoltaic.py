"""
The pycity_scheduling framework


@institution:
Institute for Automation of Complex Power Systems (ACS)
E.ON Energy Research Center
RWTH Aachen University

@author:
Sebastian Schwarz, M.Sc.
Sebastian Alexander Uerlich, B.Sc.
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.photovoltaic as pv

from pycity_scheduling.classes.electrical_entity import ElectricalEntity


class Photovoltaic(ElectricalEntity, pv.PV):
    """
    Extension of pyCity_base class PV for scheduling purposes.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    method : int
        - 0 : Calculate PV power based on an area in m^2 equipped with PV panels
        - 1 : Calculate PV power based on the installed PV peak power in kWp
    area : float, optional
        PV unit installation area in m^2 for `method=0`.
    peak_power : float, optional
        PV peak power installation in kWp for `method=1`.
    eta_noct : float, optional
        Electrical efficiency at NOCT conditions (without unit) for `method=0`.
        NOCT conditions: See manufacturer's data sheets or
        Duffie, Beckman - Solar Engineering of Thermal Processes (4th ed.), page 759
    radiation_noct : float, optional
        Nominal solar radiation at NOCT conditions (in W/m^2)
        NOCT conditions: See manufacturer's data sheets or
        Duffie, Beckman - Solar Engineering of Thermal Processes (4th ed.), page 759
    t_cell_noct : float, optional
        Nominal cell temperature at NOCT conditions (in degree Celsius)
        NOCT conditions: See manufacturer's data sheets or
        Duffie, Beckman - Solar Engineering of Thermal Processes (4th ed.), page 759
    t_ambient_noct : float, optional
        Nominal ambient air temperature at NOCT conditions (in degree Celsius)
        NOCT conditions: See manufacturer's data sheets or
        Duffie, Beckman - Solar Engineering of Thermal Processes (4th ed.), page 759
    alpha_noct : float, optional
        Temperature coefficient at NOCT conditions (without unit)
        NOCT conditions: See manufacturer's data sheets or
        Duffie, Beckman - Solar Engineering of Thermal Processes (4th ed.), page 759
    beta : float, optional
        Slope, the angle (in degree) between the plane of the surface in
        question and the horizontal. 0 <= beta <= 180. If beta > 90, the
        surface faces downwards.
    gamma : float, optional
        Surface azimuth angle. The deviation of the projection on a
        horizontal plane of the normal to the surface from the local
        meridian, with zero due south, east negative, and west positive.
        -180 <= gamma <= 180
    tau_alpha : float, optional
        Optical properties of the PV unit. Product of absorption and
        transmission coeffients.
        According to Duffie, Beckman - Solar Engineering of Thermal
        Processes (4th ed.), page 758, this value is typically close to 0.9
    force_renewables : bool, optional
        `True` if generation may not be reduced for optimization purposes.

    Notes
    -----
    The following constraint is added for removing the bounds from EE:

    .. math::
        p_{el} &=& -p_{el\\_supply}, & \\quad \\text{if force_renewables} \\\\
        0 \\geq p_{el} &\\geq& -p_{el\\_supply} , & \\quad \\text{else}
    """

    def __init__(self, environment, method, area=0.0, peak_power=0.0, eta_noct=0.18, radiation_noct=1000.0,
                 t_cell_noct=45.0, t_ambient_noct=20.0, alpha_noct=0, beta=0, gamma=0, tau_alpha=0.9,
                 force_renewables=True):
        super().__init__(environment, method, area, peak_power, eta_noct, radiation_noct, t_cell_noct, t_ambient_noct,
                         alpha_noct, beta, gamma, tau_alpha)
        self._long_ID = "PV_" + self._ID_string

        self.force_renewables = force_renewables
        self.getPower(currentValues=False)
        ts = self.timer.time_in_year(from_init=True)
        self.p_el_supply = self.total_power[ts:ts+self.simu_horizon] / 1000

    def populate_model(self, model, mode="convex", robustness=None):
        super().populate_model(model, mode)
        return

    def update_model(self, mode="", robustness=None):
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
        """Objective function of the Photovoltaic.

        Return the objective function of the photovoltaic weighted
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