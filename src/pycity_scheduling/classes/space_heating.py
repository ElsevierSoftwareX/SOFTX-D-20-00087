"""
The pycity_scheduling framework


Copyright (C) 2022,
Institute for Automation of Complex Power Systems (ACS),
E.ON Energy Research Center (E.ON ERC),
RWTH Aachen University

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import numpy as np
import pycity_base.classes.demand.space_heating as sh

from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating


class SpaceHeating(ThermalEntityHeating, sh.SpaceHeating):
    """
    Extension of pyCity_base class SpaceHeating for scheduling purposes.

    As for all uncontrollable loads, the `p_th_heat_schedule` contains the forecast
    of the load.

    Parameters
    ----------
    environment : Environment
        common to all other objects, includes time and weather instances
    method : int, optional
        - 0 : Provide load curve directly
        - 1 : Use thermal standard load profile
        - 2 : Use ISO 13790 standard to compute thermal load
    loadcurve : numpy.ndarray of float, optional
        load curve for all investigated time steps in [kW]
        requires `method=0`.
    living_area : float, optional
        living area of the apartment in m2
        requires `method=1`
    specific_demand : float, optional
        specific thermal demand of the building in [kWh /(m2*a)]
        requires `method=1`
    profile_type : str, optional
        thermal SLP profile name
        requires `method=1`
        - "HEF" : Single family household
        - "HMF" : Multi family household
        - "GBA" : Bakeries
        - "GBD" : Other services
        - "GBH" : Accomodations
        - "GGA" : Restaurants
        - "GGB" : Gardening
        - "GHA" : Retailers
        - "GHD" : Summed load profile business, trade and services
        - "GKO" : Banks, insurances, public institutions
        - "GMF" : Household similar businesses
        - "GMK" : Automotive
        - "GPD" : Paper and printing
        - "GWA" : Laundries
    zone_parameters : ZoneParameters object, optional
        parameters of the building (floor area, building class, etc.) for `method=2`.
    t_m_init : float, optional
        Initial temperature of the internal heat capacity in [°C] for `method=2`.
    ventilation : array_like, optional
        Ventilation rate in [1/h] for `method=2`.
    t_cooling_set : array_like, optional
        Cooling starts if the room temperature exceeds this value for `method=2`.
    t_heating_set : array_like, optional
        Heating starts if the room temperature drops below this value for `method=2`.
    occupancy : array_like, optional
        Full year occupancy profile for `method=2`.
    appliances : array_like, optional
        Internal gains from electrical appliances in [W] for `method=2`.
    lighting : array_like, optional
        Internal gains from lighting in Watt for `method=2`.

    Notes
    -----
    - The thermal standard load profile is based on the dissertation of Mark Hellwig
      "Entwicklung und Anwendung parametrisierter Standard-Lastprofile",
      TU München, Germany, 2003: http://mediatum.ub.tum.de/doc/601557/601557.pdf (accessed on 2020/09/28)

    - The following constraint is added for removing the bounds from TEH:

    .. math::
        p_{th\\_heat} = load\\_curve
    """

    def __init__(self, environment, method=0, loadcurve=1, living_area=0, specific_demand=0, profile_type='HEF',
                 zone_parameters=None, t_m_init=None, ventilation=0, t_cooling_set=200, t_heating_set=-50, occupancy=0,
                 appliances=0, lighting=0):

        super().__init__(environment, method, loadcurve*1000, living_area, specific_demand, profile_type,
                         zone_parameters, t_m_init, ventilation, t_cooling_set, t_heating_set, occupancy, appliances,
                         lighting)
        self._long_id = "SH_" + self._id_string

        ts = self.timer.time_in_year(from_init=True)
        p = self.loadcurve[ts:ts+self.simu_horizon] / 1000
        self.p_th_heat_schedule = p

    def update_model(self, mode=""):
        """
        Add device block to pyomo ConcreteModel.

        Set variable bounds to equal the given demand, as pure space heating does
        not provide any flexibility.

        Parameters
        ----------
        mode : str, optional
        """
        m = self.model
        timestep = self.timestep

        for t in self.op_time_vec:
            m.p_th_heat_vars[t].setlb(self.p_th_heat_schedule[timestep + t])
            m.p_th_heat_vars[t].setub(self.p_th_heat_schedule[timestep + t])
        return

    def new_schedule(self, schedule):
        super().new_schedule(schedule)
        self.copy_schedule(schedule, "default", "p_th_heat")
        return

    def update_schedule(self):
        pass

    def reset(self, schedule=None):
        pass
