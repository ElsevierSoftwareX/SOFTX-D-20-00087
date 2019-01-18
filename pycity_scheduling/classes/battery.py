import gurobi
import pycity_base.classes.supply.Battery as bat

from .battery_entity import BatteryEntity


class Battery(BatteryEntity, bat.Battery):
    """
    Extension of pycity class Battery for scheduling purposes
    """

    def __init__(self, environment, E_El_Max, SOC_Ini, SOC_End,
                 P_El_Max_Charge, P_El_Max_Discharge,
                 storage_end_equality=False):
        """

        Parameters
        ----------
        environment : Environment object
            Common Environment instance.
        E_El_Max : float
            Electric capacity of the battery [kWh].
        SOC_Ini : float
            Iinitial state of charge.
        SOC_End : float
            Final state of charge.
        P_El_Max_Charge : float
            Maximum charging power [kW].
        P_El_Max_Discharge : float
            Maximum discharging power [kW].
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        super(Battery, self).__init__(environment.timer, E_El_Max,
                                      SOC_Ini, SOC_End, P_El_Max_Charge,
                                      P_El_Max_Discharge, environment, SOC_Ini,
                                      E_El_Max*3600*1000, 0, 0.9, 0.9)
        self._kind = "battery"
        self._long_ID = "BAT_" + self._ID_string

        self.storage_end_equality = storage_end_equality

    def populate_model(self, model, mode=""):
        super(Battery, self).populate_model(model, mode)

        for t in range(1, self.op_horizon):
            model.addConstr(
                0.9 * self.E_El_vars[t]
                == 0.9 * self.E_El_vars[t-1]
                   + (0.81*self.P_El_Demand_vars[t] - self.P_El_Supply_vars[t])
                     * self.time_slot
            )
        self.E_El_vars[-1].lb = self.E_El_Max * self.SOC_End
        if self.storage_end_equality:
            self.E_El_vars[-1].ub = self.E_El_Max * self.SOC_End

    def update_model(self, model, mode=""):
        # raises GurobiError if constraint is from a prior scheduling
        # optimization or not present
        try:
            model.remove(self.E_El_Init_constr)
        except gurobi.GurobiError:
            pass
        timestep = self.timer.currentTimestep
        if timestep == 0:
            E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            E_El_Ini = self.E_El_Actual_Schedule[timestep - 1]
        self.E_El_Init_constr = model.addConstr(
            0.9 * self.E_El_vars[0]
            == 0.9 * E_El_Ini
               + (0.81*self.P_El_Demand_vars[0] - self.P_El_Supply_vars[0])
                 * self.time_slot
        )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the battery wheighted with coeff.
        Standard quadratic term.

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
        obj.addTerms(
            [coeff] * self.op_horizon,
            self.P_El_vars,
            self.P_El_vars
        )
        return obj
