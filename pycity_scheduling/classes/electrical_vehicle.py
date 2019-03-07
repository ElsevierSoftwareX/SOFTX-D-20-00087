import gurobipy as gurobi
import numpy as np
import warnings

from .battery import Battery


class ElectricalVehicle(Battery):
    """
    Class representing an electrical vehicle for scheduling purposes.
    """

    def __init__(self, environment, E_El_Max, P_El_Max_Charge,
                 SOC_Ini, charging_time=None):
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
        charging_time : array of binaries
            Indicator when electrical vehicle be charged.
            `charging_time[t] == 0`: EV cannot be charged in t
            `charging_time[t] == 1`: EV can be charged in t
            Length should match `environment.timer.simu_horizon`, otherwise it
            will be turncated / repeated to match it.
        """
        super(ElectricalVehicle, self).__init__(
            environment, E_El_Max, SOC_Ini,
            P_El_Max_Charge, eta=1, storage_end_equality=False
        )
        self._kind = "electricalvehicle"
        self._long_ID = "EV_" + self._ID_string

        if charging_time is None:
            # load during night, drive at day
            a = int(86400 / self.time_slot / 4)
            b = int(86400 / self.time_slot / 2)
            c = int(86400 / self.time_slot) - a - b
            charging_time = [1]*a + [0]*b + [1]*c
        elif len(charging_time) != self.simu_horizon:
            warnings.warn(
                "Length of `charging_time` does not match `simu_horizon`. "
                "Expected length: {}, actual length: {}"
                .format(self.simu_horizon, len(charging_time))
            )

        self.charging_time = np.resize(charging_time, self.simu_horizon)

        self.P_El_Drive_vars = []
        self.E_El_SOC_constrs = []

    def populate_model(self, model, mode=""):
        super(ElectricalVehicle, self).populate_model(model, mode)

        self.P_El_Drive_vars = []
        # Simulate power consumption while driving
        for t in self.op_time_vec:
            self.P_El_Drive_vars.append(
                model.addVar(
                    name="%s_P_El_Drive_at_t=%i" % (self._long_ID, t + 1)
                )
            )
        model.update()

        # Replace coupling constraints from Battery class
        model.remove(self.E_El_coupl_constrs)
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

        delta = (
            (self.etaCharge * self.P_El_Demand_vars[0]
             - (1 / self.etaDischarge) * self.P_El_Supply_vars[0]
             - self.P_El_Drive_vars[0])
            * self.time_slot
        )
        self.E_El_Init_constr = model.addConstr(
            self.E_El_vars[0] == E_El_Ini + delta
        )

        model.remove(self.E_El_SOC_constrs)

        for t in self.op_time_vec:
            if self.charging_time[timestep+t]:
                self.P_El_vars[t].lb = -self.P_El_Max_Charge
                self.P_El_Drive_vars.ub = 0
                if t < self.op_horizon - 1:
                    if not self.charging_time[timestep+t+1]:
                        self.E_El_SOC_constrs.append(model.addConstr(
                            self.E_El_vars[t] == self.E_El_Max
                        ))
            else:
                self.P_El_vars[t].lb = 0
                self.P_El_Drive_vars.ub = gurobi.GRB.INFINITY
                if t < self.op_horizon - 1:
                    if self.charging_time[timestep+t+1]:
                        self.E_El_SOC_constrs.append(model.addConstr(
                            self.E_El_vars[t] == 0
                        ))

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
