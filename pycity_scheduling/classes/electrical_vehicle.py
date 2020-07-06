import numpy as np
import pyomo.environ as pyomo
from pyomo.core.expr.numeric_expr import ExpressionBase

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
        super().__init__(environment, E_El_max, P_El_max_charge, P_El_max_charge, soc_init, eta=1,
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

        self.new_var("P_El_Drive")

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method. Replace coupling
        constraints from Battery class with coupling constraints
        of EV. Simulate power consumption while driving.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)
        m = self.model

        # Simulate power consumption while driving
        m.P_El_Drive_vars = pyomo.Var(m.t, domain=pyomo.NonNegativeReals, bounds=(0, None), initialize=0)

        # Replace coupling constraints from Battery class
        m.del_component("E_constr")
        m.del_component("E_end_constr")
        def e_rule(model, t):
            delta = (
                (self.etaCharge * model.P_El_Demand_vars[t]
                 - (1/self.etaDischarge) * model.P_El_Supply_vars[t]
                 - model.P_El_Drive_vars[t])
                * self.time_slot
            )
            E_El_last = model.E_El_vars[t - 1] if t >= 1 else model.E_El_ini
            return model.E_El_vars[t] == E_El_last + delta
        m.E_constr = pyomo.Constraint(m.t, rule=e_rule)

    def update_model(self, mode=""):
        m = self.model

        timestep = self.timestep
        if timestep == 0:
            m.E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            m.E_El_Ini = self.E_El_Schedule[timestep-1]

        charging_time = self.charging_time[self.op_slice]

        # Reset E_El bounds
        for t in self.op_time_vec:
            m.E_El_vars[t].setub(self.E_El_Max)
            m.E_El_vars[t].setlb(0)

        for t in self.op_time_vec:
            if charging_time[t]:
                m.P_El_Demand_vars[t].setub(self.P_El_Max_Charge)
                m.P_El_Supply_vars[t].setub(self.P_El_Max_Discharge)
                m.P_El_Drive_vars[t].setub(0)
            else:
                m.P_El_Demand_vars[t].setub(0)
                m.P_El_Supply_vars[t].setub(0)
                m.P_El_Drive_vars[t].setub(None)
            if t + 1 < self.op_horizon:
                if charging_time[t] and not charging_time[t+1]:
                    # Full battery at end of charging period
                    m.E_El_vars[t].setub(self.E_El_Max)
                    m.E_El_vars[t].setlb(self.E_El_Max)

                    # Empty battery
                    m.E_El_vars[t + 1].setub(0.2 * self.E_El_Max)
                    m.E_El_vars[t + 1].setlb(0.2 * self.E_El_Max)

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
            m.E_El_vars[self.op_horizon-1].setub(portion * self.E_El_Max)
            m.E_El_vars[self.op_horizon-1].setlb(portion * self.E_El_Max)

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
        ExpressionBase :
            Objective function.
        """
        m = self.model
        c = np.array(list(map(lambda x: x+1, range(self.op_horizon))))
        c = c * (coeff * self.op_horizon / sum(c))
        return pyomo.sum_product(c, m.P_El_vars, m.P_El_vars)
