import numpy as np
import pyomo.environ as pyomo

import pycity_base.classes.demand.SpaceHeating as sh

from .thermal_entity import ThermalEntity
from pycity_scheduling import util


class SpaceHeating(ThermalEntity, sh.SpaceHeating):
    """
    Extension of pyCity_base class SpaceHeating for scheduling purposes.

    As for all uncontrollable loads, the `P_Th_Schedule` contains the forecast
    of the load.
    """

    def __init__(self, environment, method=0, loadcurve=1, livingArea=0,
                 specificDemand=0, profile_type='HEF', zoneParameters=None,
                 T_m_init=None, ventilation=0, TCoolingSet=200,
                 THeatingSet=-50, occupancy=0, appliances=0, lighting=0):
        """
        Parameters
        ----------
        environment : Environment
            common to all other objects, includes time and weather instances
        method : {0, 1, 2}, optional
            - 0 : Provide load curve directly
            - 1 : Use thermal standard load profile
            - 2 : Use ISO 13790 standard to compute thermal load
        loadcurve : numpy.ndarray of float, optional
            load curve for all investigated time steps in [kW]
            requires `method=0`.
        livingArea : float, optional
            living area of the apartment in m2
            requires `method=1`
        specificDemand : float, optional
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
        zoneParameters : ZoneParameters object, optional
            parameters of the building (floor area, building class, etc.).
            requires `method=2`
        T_m_init : float, optional
            initial temperature of the internal heat capacity in [?]
            requires `method=2`
        ventilation : array_like, optional
            ventilation rate in [1/h]
            requires `method=2`
        TCoolingSet : array_like, optional
            cooling starts if the room temperature exceeds this value
            requires `method=2`
        THeatingSet : array_like, optional
            heating starts if the room temperature drops below this value
            requires `method=2`
        occupancy : array_like, optional
            full year occupancy profile
            requires `method=2`
        appliances : array_like, optional
            internal gains from electrical appliances in [W]
            requires `method=2`
        lighting : array_like, optional
            internal gains from lighting in Watt
            requires `method=2`

        Notes
        -----
         - the thermal standard load profile is based on the disseratation of
           Mark Hellwig
           "Entwicklung und Anwendung parametrisierter Standard-Lastprofile",
           TU München, Germany, 2003:
           http://mediatum.ub.tum.de/doc/601557/601557.pdf
        """

        super().__init__(environment, method, loadcurve*1000, livingArea, specificDemand, profile_type, zoneParameters,
                         T_m_init, ventilation, TCoolingSet, THeatingSet, occupancy, appliances, lighting)
        self._long_ID = "SH_" + self._ID_string

        ts = self.timer.time_in_year(from_init=True)
        p = self.loadcurve[ts:ts+self.simu_horizon] / 1000
        self.P_Th_Schedule = p

    def update_model(self, mode=""):
        """Add device block to pyomo ConcreteModel.

        Set variable bounds to equal the given demand, as pure space heating does
        not provide any flexibility.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
        """
        m = self.model
        timestep = self.timestep

        for t in self.op_time_vec:
            m.P_Th_vars.setlb(self.P_Th_Schedule[timestep + t])
            m.P_Th_vars.setub(self.P_Th_Schedule[timestep + t])

    def new_schedule(self, schedule):
        super().new_schedule(schedule)
        self.copy_schedule(schedule, "default", "P_Th")

    def update_schedule(self, mode=""):
        pass

    def reset(self, name=None):
        pass
