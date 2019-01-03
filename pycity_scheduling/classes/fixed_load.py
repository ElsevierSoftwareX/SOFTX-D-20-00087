import pycity_base.classes.demand.ElectricalDemand as ed

from .electrical_entity import ElectricalEntity


class FixedLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
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
        super(FixedLoad, self).__init__(environment.timer, environment,
                                        method, demand*1000, annualDemand,
                                        profileType, singleFamilyHouse,
                                        total_nb_occupants,
                                        randomizeAppliances,
                                        lightConfiguration, occupancy)
        self._long_ID = "FL_" + self._ID_string
        self.annualDemand = annualDemand

        if method == 0:
            self.P_El_Demand = demand
        else:
            self.P_El_Demand = self.loadcurve / 1000

    def update_model(self, model, mode=""):
        timestep = self.timer.currentTimestep
        for t in range(self.timer.timestepsUsedHorizon):
            self.P_El_vars[t].lb = self.P_El_Demand[t+timestep]
            self.P_El_vars[t].ub = self.P_El_Demand[t+timestep]
