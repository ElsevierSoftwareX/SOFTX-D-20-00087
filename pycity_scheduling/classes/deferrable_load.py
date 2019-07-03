import numpy as np
import gurobipy as gurobi
import pycity_base.classes.demand.ElectricalDemand as ed

from .electrical_entity import ElectricalEntity
from pycity_scheduling import util


class DeferrableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
    """

    def __init__(self, environment, P_El_Nom, E_Min_Consumption,
                 load_time=None, lt_pattern=None):
        """Initialize DeferrableLoad.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        P_El_Nom : float
            Nominal elctric power in [kW].
        E_Min_Consumption : float
             Minimal power to be consumed over the time in [kWh].
        load_time : array of binaries
            Indicator when deferrable load can be turned on.
            `load_time[t] == 0`: device is off in t
            `load_time[t] == 1`: device can be turned on in t
            It must contain at least one `0` otherwise the model will become
            infeasible. Its length has to be consistent with `lt_pattern`.
        lt_pattern : str, optional
            Define how the `load_time` profile is to be used
            `None` : Profile matches simulation horizon.
            'daily' : Profile matches one day.
            'weekly' : Profile matches one week.

        Raises
        ------
        ValueError :
            If `lt_pattern` does not match `load_time`.
        """
        shape = environment.timer.timestepsTotal
        super(DeferrableLoad, self).__init__(environment.timer, environment, 0,
                                             np.zeros(shape))

        self._long_ID = "DL_" + self._ID_string

        self.P_El_Nom = P_El_Nom
        self.E_Min_Consumption = E_Min_Consumption
        self.load_time = util.compute_profile(self.timer, load_time,
                                              lt_pattern)

        self.P_El_bvars = []
        self.P_El_Sum_constrs = []

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model

        Call parent's `populate_model` method and set the upper bounds to the
        nominal power or zero depending on `self.time`. Also set a constraint
        for the minimum load. If mode == 'binary' add binary variables to model
        load as one block that can be shifted in time.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(DeferrableLoad, self).populate_model(model, mode)

        # device is on or off
        if mode == "Binary":
            self.P_El_bvars = []

            # Add variables:
            for t in self.op_time_vec:
                self.P_El_bvars.append(
                    model.addVar(
                        vtype=gurobi.GRB.BINARY,
                        name="%s_binary_at_t=%i"
                             % (self._long_ID, t+1)
                    )
                )
            model.update()

            # Set additional constraints:
            for t in self.op_time_vec:
                model.addConstr(
                    self.P_El_vars[t] <= self.P_El_bvars[t] * 1000000
                )
            model.addConstr(
                gurobi.quicksum(
                    (self.P_El_bvars[t] - self.P_El_bvars[t+1])
                    * (self.P_El_bvars[t] - self.P_El_bvars[t+1])
                    for t in range(self.op_horizon - 1))
                <= 2
            )

    def update_model(self, model, mode=""):
        # raises GurobiError if constraints are from a prior scheduling
        # optimization
        try:
            model.remove(self.P_El_Sum_constrs)
        except gurobi.GurobiError:
            pass
        del self.P_El_Sum_constrs[:]

        timestep = self.timestep
        load_time = self.load_time[self.op_slice]
        completed_load = 0
        if load_time[0]:
            for val in self.P_El_Schedule[:timestep][::-1]:
                if val > 0:
                    completed_load += val
                else:
                    break
            completed_load *= self.time_slot
        lin_term = gurobi.LinExpr()

        for t in self.op_time_vec:
            if load_time[t]:
                self.P_El_vars[t].ub = self.P_El_Nom
                lin_term += self.P_El_vars[t]
            else:
                self.P_El_vars[t].ub = 0
                if lin_term.size() > 0:
                    self.P_El_Sum_constrs.append(
                        model.addConstr(
                            lin_term * self.time_slot
                            == self.E_Min_Consumption - completed_load
                        )
                    )
                    completed_load = 0
                    lin_term = gurobi.LinExpr()

        if lin_term.size() > 0:
            current_ts = timestep + self.op_horizon
            first_ts = current_ts
            while True:
                first_ts -= 1
                if not self.load_time[first_ts-1]:
                    break
            last_ts = timestep + self.op_horizon
            while last_ts < self.simu_horizon:
                if not self.load_time[last_ts]:
                    break
                last_ts += 1
            portion = (current_ts - first_ts) / (last_ts - first_ts)
            self.P_El_Sum_constrs.append(model.addConstr(
                lin_term * self.time_slot == portion * self.E_Min_Consumption
            ))

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the deferrable load wheighted with
        coeff. Quadratic term minimizing the deviation from the optiaml
        loadcurve.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        max_loading_time = sum(self.time) * self.time_slot
        optimal_P_El = self.E_Min_Consumption / max_loading_time
        obj = gurobi.QuadExpr()
        obj.addTerms(
            [coeff] * self.op_horizon,
            self.P_El_vars,
            self.P_El_vars
        )
        obj.addTerms(
            [- 2 * coeff * optimal_P_El] * self.op_horizon,
            self.P_El_vars
        )
        return obj

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        self.P_El_Act_var.lb = self.P_El_Schedule[timestep]
        self.P_El_Act_var.ub = self.P_El_Schedule[timestep]
