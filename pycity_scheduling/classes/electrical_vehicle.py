import gurobipy as gurobi
import numpy as np

from .battery import Battery
from pycity_scheduling import util


class ElectricalVehicle(Battery):
    """
    Class representing an electrical vehicle for scheduling purposes.
    """

    def __init__(self, environment, E_El_max, P_El_max_charge,
                 soc_init=0.5, charging_time=None, ct_pattern=None):
        """Initialize ElectricalVehicle.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        E_El_max : float
            Electric capacity of the battery in [kWh].
        P_El_max_charge : float
            Maximum charging power in [kW].
        soc_init : float, optional
            Initial state of charge. Defaults to 50%.
        charging_time : array of binaries
            Indicator when electrical vehicle can be charged.
            `charging_time[t] == 0`: EV cannot be charged in t
            `charging_time[t] == 1`: EV can be charged in t
            It must contain at least one `0` otherwise the model will become
            infeasible. Its length has to be consistent with `ct_pattern`.
        ct_pattern : str, optional
            Define how the `charging_time` profile is to be used
            `None` : Profile matches simulation horizon.
            'daily' : Profile matches one day.
            'weekly' : Profile matches one week.
        """
        super(ElectricalVehicle, self).__init__(environment, E_El_max,
                                                P_El_max_charge,
                                                P_El_max_charge,
                                                soc_init, eta=1,
                                                storage_end_equality=False)
        self._kind = "electricalvehicle"
        self._long_ID = "EV_" + self._ID_string

        if charging_time is None:
            # load at night, drive during day
            ts_per_day = int(86400 / self.time_slot)
            a = int(ts_per_day / 4)
            b = int(ts_per_day / 2)
            c = ts_per_day - a - b
            charging_time = [1] * a + [0] * b + [1] * c
            ct_pattern = 'daily'
        self.charging_time = util.compute_profile(self.timer, charging_time,
                                                  ct_pattern)

        self.P_El_Drive_vars = []
        self.E_El_SOC_constrs = []

    def populate_model(self, model, mode="convex"):
        """Add variables and constraints to Gurobi model.

        Call parent's `populate_model` method. Replace coupling
        constraints from Battery class with coupling constraints
        of EV. Simulate power consumption while driving.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super(ElectricalVehicle, self).populate_model(model, mode)

        # Simulate power consumption while driving
        self.P_El_Drive_vars = []
        for t in self.op_time_vec:
            self.P_El_Drive_vars.append(
                model.addVar(
                    name="%s_P_El_Drive_at_t=%i" % (self._long_ID, t + 1)
                )
            )
        model.update()

        # Replace coupling constraints from Battery class
        model.remove(self.E_El_coupl_constrs)
        del self.E_El_coupl_constrs[:]
        for t in range(1, self.op_horizon):
            delta = (
                (self.etaCharge * self.P_El_Demand_vars[t]
                 - (1/self.etaDischarge) * self.P_El_Supply_vars[t]
                 - self.P_El_Drive_vars[t])
                * self.time_slot
            )
            self.E_El_coupl_constrs.append(model.addConstr(
                self.E_El_vars[t] == self.E_El_vars[t-1] + delta
            ))
        self.E_El_vars[-1].lb = 0
        self.E_El_vars[-1].ub = self.E_El_Max

    def update_model(self, model, mode=""):
        # raises GurobiError if constraints are from a prior scheduling
        # optimization
        try:
            model.remove(self.E_El_Init_constr)
        except gurobi.GurobiError:
            pass
        timestep = self.timestep
        if timestep == 0:
            E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            E_El_Ini = self.E_El_Schedule[timestep-1]
        delta = (
            (self.etaCharge * self.P_El_Demand_vars[0]
             - (1 / self.etaDischarge) * self.P_El_Supply_vars[0]
             - self.P_El_Drive_vars[0])
            * self.time_slot
        )
        self.E_El_Init_constr = model.addConstr(
            self.E_El_vars[0] == E_El_Ini + delta
        )

        try:
            model.remove(self.E_El_SOC_constrs)
        except gurobi.GurobiError:
            pass
        del self.E_El_SOC_constrs[:]
        charging_time = self.charging_time[self.op_slice]
        for t in self.op_time_vec:
            if charging_time[t]:
                self.P_El_Demand_vars[t].ub = self.P_El_Max_Charge
                self.P_El_Supply_vars[t].ub = self.P_El_Max_Discharge
                self.P_El_Drive_vars[t].ub = 0
            else:
                self.P_El_Demand_vars[t].ub = 0
                self.P_El_Supply_vars[t].ub = 0
                self.P_El_Drive_vars[t].ub = gurobi.GRB.INFINITY
            if t + 1 < self.op_horizon:
                if charging_time[t] and not charging_time[t+1]:
                    self.E_El_SOC_constrs.append(model.addConstr(
                        self.E_El_vars[t] == self.E_El_Max,
                        "Full battery at end of charging period"
                    ))
                if not charging_time[t+1] and charging_time[t]:
                    self.E_El_SOC_constrs.append(model.addConstr(
                        self.E_El_vars[t+1] == 0.2 * self.E_El_Max,
                        "Empty battery"
                    ))

        if charging_time[-1]:
            current_ts = timestep + self.op_horizon
            first_ts = current_ts
            while True:
                first_ts -= 1
                if not self.charging_time[first_ts-1]:
                    break
            last_ts = timestep + self.op_horizon
            while True:
                if not self.charging_time[last_ts%self.simu_horizon]:
                    break
                last_ts += 1
            portion = (current_ts - first_ts) / (last_ts - first_ts)
            self.E_El_SOC_constrs.append(model.addConstr(
                self.E_El_vars[self.op_horizon-1] == portion * self.E_El_Max,
                "SOC at the end"
            ))

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the electric vehicle wheighted with
        coeff. Quadratic term with additional weights to reward charging the
        vehicle earlier.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        c = np.array(list(map(lambda x: x+1, range(self.op_horizon))))
        c = c * (coeff * self.op_horizon / sum(c))
        obj = gurobi.QuadExpr()
        obj.addTerms(
            c,
            self.P_El_vars,
            self.P_El_vars
        )
        return obj

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        super(ElectricalVehicle, self).update_deviation_model(model, timestep,
                                                              '')
