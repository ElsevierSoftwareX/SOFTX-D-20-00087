import pycity_base.classes.demand.DomesticHotWater as dhw

from .thermal_entity import ThermalEntity


class DomesticHotWater(ThermalEntity, dhw.DomesticHotWater):
    """
    Extension of pycity class DomesticHotWater for scheduling purposes.
    """

    def __init__(self, environment, tFlow, thermal=True, method=0,
                 loadcurve=None, dailyConsumption=0, supplyTemperature=0,
                 occupancy=None):
        """Initialize DomesticHotWater.

        Parameters
        ----------
        environment : Environment
            common to all other objects, includes time and weather instances
        tFlow : float
            flow temperature of domestic hot water in [°C]
        thermal : bool, optional
            DHW provided electrically (False) or via thermal energy storage
            (True)
        method : {0, 1, 2}, optional
            - 0 : provide load curve directly (for all timesteps!)
            - 1 : load profile from Annex 42
            - 2 : stochastical method
        loadcurve : numpy.ndarray, optional
            load curve for all investigated time steps in [W]
            requires `method=0`
        dailyConsumption : float, optional
            average, total domestic hot water consumption in [l/d]
            requires `method=1`
        supplyTemperature : float, optional
            supply temperature in [°C]
            necessary to compute the heat load that results from each liter
            consumption
            requires `method=1`

        Notes
        -----
         - the load profiles from Annex 42 can be found here:
           http://www.ecbcs.org/annexes/annex42.htm
        """
        super(DomesticHotWater, self).__init__(environment.timer, environment,
                                               tFlow, thermal, method,
                                               loadcurve, dailyConsumption,
                                               supplyTemperature, occupancy)
        self._long_ID = "DHW_" + self._ID_string

        self.P_Th_Demand = self.loadcurve / 1000

    def update_model(self, model, mode=""):
        timestep = self.timer.currentTimestep
        for t in self.op_time_vec:
            self.P_Th_vars[t].lb = self.P_Th_Demand[t+timestep]
            self.P_Th_vars[t].ub = self.P_Th_Demand[t+timestep]
