import numpy as np
import pyomo.environ as pyomo

import pycity_base.classes.demand.ElectricalDemand as ed

from pycity_scheduling.classes.electrical_entity import ElectricalEntity
from pycity_scheduling import util


class FixedLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pyCity_base class ElectricalDemand for scheduling purposes.

    As for all uncontrollable loads, the `P_El_Schedule` contains the forecast
    of the load.
    """

    def __init__(self, environment, method=0, demand=0, annualDemand=0,
                 profileType="H0", singleFamilyHouse=True,
                 total_nb_occupants=0, randomizeAppliances=True,
                 lightConfiguration=0, occupancy=None):
        """Initialize FixedLoad.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        method : {0, 1, 2}, optional
            - 0 : provide load curve directly
            - 1 : standard load profile (for households)
            - 2 : stochastic electrical load model
        demand : numpy.ndarray of float, optional
            Demand for all investigated time steps in [kW].
            requires `method=0`
        annualDemand : float
            Required for SLP and recommended for method 2.
            Annual electrical demand in [kWh].
            If method 2 is chosen but no value is given, a standard value for
            Germany (http://www.die-stromsparinitiative.de/fileadmin/bilder/
            Stromspiegel/Brosch%C3%BCre/Stromspiegel2014web_final.pdf) is used.
        profileType : String (required for SLP)
            - H0 : Household
            - L0 : Farms
            - L1 : Farms with breeding / cattle
            - L2 : Farms without cattle
            - G0 : Business (general)
            - G1 : Business (workingdays 8:00 AM - 6:00 PM)
            - G2 : Business with high loads in the evening
            - G3 : Business (24 hours)
            - G4 : Shops / Barbers
            - G5 : Bakery
            - G6 : Weekend operation
        total_nb_occupants : int, optional
            Number of people living in the household.
            requires `method=2`
        randomizeAppliances : bool, optional
            - True : distribute installed appliances randomly
            - False : use the standard distribution
            requires `method=2`
        lightConfiguration : {0..99}, optional
            There are 100 light bulb configurations predefined for the
            stochastic model.
            requires `method=2`
        occupancy : int, optional
            Occupancy given at 10-minute intervals for a full year.
            requires `method=2`

        Notes
        -----
         - the standard load profile can be downloaded here:
           http://www.ewe-netz.de/strom/1988.php

         - average German electricity consumption per household can be found
           here:
           http://www.die-stromsparinitiative.de/fileadmin/bilder/Stromspiegel/
           Brosch%C3%BCre/Stromspiegel2014web_final.pdf
        """
        super().__init__(environment, method, demand*1000, annualDemand, profileType, singleFamilyHouse,
                         total_nb_occupants, randomizeAppliances, lightConfiguration, occupancy)
        self._long_ID = "FL_" + self._ID_string

        ts = self.timer.time_in_year(from_init=True)
        p = self.loadcurve[ts:ts+self.simu_horizon] / 1000
        self.P_El_Schedule = p

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        for t in self.op_time_vec:
            m.P_El_vars.setlb(self.P_El_Schedule[timestep + t])
            m.P_El_vars.setub(self.P_El_Schedule[timestep + t])

    def new_schedule(self, schedule):
        super().new_schedule(schedule)
        self.copy_schedule(schedule, "default", "P_El")

    def update_schedule(self, mode=""):
        pass

    def reset(self, name=None):
        pass
