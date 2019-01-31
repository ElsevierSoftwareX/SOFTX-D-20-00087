import numpy as np
import gurobi
import pycity_base.classes.demand.ElectricalDemand as ed

from ..exception import PyCitySchedulingInitError
from ..util import compute_blocks
from .electrical_entity import ElectricalEntity


class DeferrableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
    """

    def __init__(self, environment, P_El_Nom, E_Min_Consumption, time):
        """Initialize DeferrableLoad.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        P_El_Nom : float
            Nominal elctric power in [kW].
        E_Min_Consumption : float
             Minimal power to be consumed over the time in [kWh].
        time : array of binaries
            Indicator when deferrable load can be turned on.
            `time[t] == 0`: device is off in t
            `time[t] == 1`: device *can* be turned on in t
            `time` must contain at least one `0` otherwise the model will
            become infeasible.
        """
        shape = environment.timer.timestepsTotal
        super(DeferrableLoad, self).__init__(environment.timer, environment, 0,
                                             np.zeros(shape))

        self._long_ID = "DL_" + self._ID_string

        if len(time) != 86400 / self.timer.timeDiscretization:
            raise PyCitySchedulingInitError(
                "The `time` argument must hold as many values as one day "
                "has timesteps."
            )
        self.P_El_Nom = P_El_Nom
        self.E_Min_Consumption = E_Min_Consumption
        self.time = time
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
        timestep = self.timer.currentTimestep
        for t in self.op_time_vec:
            self.P_El_vars[t].ub = 0

        blocks, portion = compute_blocks(self.timer, self.time)
        if len(blocks) == 0:
            return
        # raises GurobiError if constraints are from a prior scheduling
        # optimization
        try:
            for constr in self.P_El_Sum_constrs:
                model.remove(constr)
        except gurobi.GurobiError:
            pass
        del self.P_El_Sum_constrs[:]
        # consider already completed consumption
        completed_load = 0
        if blocks[0][0] == 0:
            for val in self.P_El_Actual_Schedule[:timestep][::-1]:
                if val > 0:
                    completed_load += val
                else:
                    break
            completed_load *= self.time_slot
        # consider future consumption
        consumption = self.E_Min_Consumption
        if len(blocks) == 1:
            consumption *= portion
        block_vars = self.P_El_vars[blocks[0][0]:blocks[0][1]]
        for var in block_vars:
            var.ub = self.P_El_Nom
        self.P_El_Sum_constrs.append(
            model.addConstr(
                gurobi.quicksum(block_vars) * self.time_slot
                == consumption - completed_load
            )
        )
        for block in blocks[1:-1]:
            block_vars = self.P_El_vars[block[0]:block[1]]
            for var in block_vars:
                var.ub = self.P_El_Nom
            self.P_El_Sum_constrs.append(
                model.addConstr(
                    gurobi.quicksum(block_vars) * self.time_slot
                    == self.E_Min_Consumption
                )
            )
        if len(blocks) > 1:
            block_vars = self.P_El_vars[blocks[-1][0]:blocks[-1][1]]
            for var in block_vars:
                var.ub = self.P_El_Nom
            self.P_El_Sum_constrs.append(
                model.addConstr(
                    gurobi.quicksum(block_vars) * self.time_slot
                    == self.E_Min_Consumption * portion
                )
            )

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
