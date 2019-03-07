import gurobipy as gurobi

from .battery_entity import BatteryEntity
from ..util import compute_blocks, compute_inverted_blocks


class ElectricalVehicle(BatteryEntity):
    """
    Class representing an electrical vehicle for scheduling purposes.
    """

    def __init__(self, environment, E_El_Max, P_El_Max_Charge,
                 SOC_Ini, SOC_End, charging_time=None):
        """Initialize ElectricalVehicle.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        E_El_Max : float
            Electric capacity of the battery in [kWh].
        P_El_Max_Charge : float
            Maximum charging power in [kW].
        SOC_Ini : float
            Initial state of charge.
        SOC_End : float
            Final state of charge.
        charging_time : array of binaries
            Indicator when electrical vehicle be charged.
            `charging_time[t] == 0`: EV cannot be charged in t
            `charging_time[t] == 1`: EV *can* be charged in t
        """
        super(ElectricalVehicle, self).__init__(
            environment.timer, E_El_Max, SOC_Ini, SOC_End,
            P_El_Max_Charge, 0
        )
        self._kind = "electricalvehicle"
        self._long_ID = "EV_" + self._ID_string

        if charging_time is None:
            # load during night, drive at day
            a = int(86400 / self.timer.timeDiscretization / 4)
            b = int(86400 / self.timer.timeDiscretization / 2)
            c = int(86400 / self.timer.timeDiscretization - (a + b))
            charging_time = [1] * a + [0] * b + [1] * c

        t1 = self.timer.time_in_day()
        t2 = t1 + self.simu_horizon
        ts_in_day = int(86400 / self.timer.timeDiscretization)
        self.charging_time = []
        for t in range(t1, t2):
            self.charging_time.append(charging_time[t%ts_in_day])

        self.P_El_Drive_vars = []
        self.P_El_Sum_constrs = []

    def populate_model(self, model, mode=""):
        super(ElectricalVehicle, self).populate_model(model, mode)

        self.P_El_Drive_vars = []
        for t in self.op_time_vec:
            self.P_El_Drive_vars.append(
                model.addVar(
                    name="%s_P_El_Drive_at_t=%i" % (self._long_ID, t + 1)
                )
            )
        model.update()

        for t in range(1, self.op_horizon):
            model.addConstr(
                0.9 * self.E_El_vars[t]
                == 0.9 * self.E_El_vars[t-1]
                   + (0.81*self.P_El_Demand_vars[t] - self.P_El_Supply_vars[t]
                      - 0.9*self.P_El_Drive_vars[t])
                     * self.time_slot
            )

    def update_model(self, model, mode=""):
        super(ElectricalVehicle, self).update_model(model, mode)

        try:
            model.remove(self.E_El_Init_constr)
        except gurobi.GurobiError:
            # raises GurobiError if constraint is from a prior scheduling
            # optimization or not present
            pass
        timestep = self.timer.currentTimestep
        if timestep == 0:
            E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            E_El_Ini = self.E_El_Schedule[timestep-1]
        self.E_El_Init_constr = model.addConstr(
            0.9 * self.E_El_vars[0]
            == 0.9 * E_El_Ini
               + (0.81*self.P_El_Demand_vars[0] - self.P_El_Supply_vars[0]
                  - 0.9*self.P_El_Drive_vars[0])
                 * self.time_slot
        )

        blocks, portion = compute_blocks(self.timer, self.charging_time)
        if len(blocks) == 0:
            return
        for block in blocks[0:-1]:
            t1 = block[0]
            t2 = block[1]
            self._reset_vars(t1, t2)
            self.E_El_vars[t2-1].lb = self.E_El_Max
            self.E_El_vars[t2-1].ub = self.E_El_Max
        t1 = blocks[-1][0]
        t2 = blocks[-1][1]
        self._reset_vars(t1, t2)
        self.E_El_vars[t2-1].lb = self.E_El_Max * portion
        self.E_El_vars[t2-1].ub = self.E_El_Max * portion

        blocks, portion = compute_inverted_blocks(self.timer,
                                                  self.charging_time)
        if len(blocks) == 0:
            return
        for block in blocks[0:-1]:
            t1 = block[0]
            t2 = block[1]
            self._reset_vars(t1, t2, True)
            self.E_El_vars[t2-1].lb = 0
            self.E_El_vars[t2-1].ub = 0
        t1 = blocks[-1][0]
        t2 = blocks[-1][1]
        self._reset_vars(t1, t2, True)
        self.E_El_vars[t2-1].lb = self.E_El_Max * (1 - portion)
        self.E_El_vars[t2-1].ub = self.E_El_Max * (1 - portion)

    def _reset_vars(self, t1, t2, drive_vars=False):
        max_power = self.E_El_Max/self.time_slot
        for var in self.P_El_vars[t1:t2]:
            var.ub = 0 if drive_vars else max_power
        for var in self.P_El_Drive_vars[t1:t2]:
            var.ub = max_power if drive_vars else 0
        for var in self.E_El_vars[t1:t2-1]:
            var.lb = 0
            var.ub = self.E_El_Max

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the electric vehicle wheighted with
        coeff. Quadratic term with additional wieghts to reward
        charging the vehicle earlier.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        i = int(self.op_horizon / 5)
        c = [1.4] * i + [1.2] * i + [1] * (self.op_horizon - 4 * i) + [0.8] * i + [0.6] * i
        obj = gurobi.QuadExpr()
        obj.addTerms(
            [coeff * v for v in c],
            self.P_El_vars,
            self.P_El_vars
        )
        return obj
