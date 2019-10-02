import numpy as np
import gurobipy as gurobi
import pycity_base.classes.demand.ElectricalDemand as ed

from warnings import warn
from .electrical_entity import ElectricalEntity
from pycity_scheduling import util


class DeferrableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
    """

    def __init__(self, environment, P_El_Nom, E_Consumption,
                 load_time=None, lt_pattern=None):
        """Initialize DeferrableLoad.
        The Load will always run once in the op_horizon

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        P_El_Nom : float
            Nominal elctric power in [kW].
        E_Consumption : float
             Power to be consumed over the op_horizon in [kWh].
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
        super().__init__(environment, 0, np.zeros(shape))

        self._long_ID = "DL_" + self._ID_string

        self.P_El_Nom = P_El_Nom
        self.E_Consumption = E_Consumption
        self.load_time = util.compute_profile(self.timer, load_time,
                                              lt_pattern)
        if len(load_time) != self.op_horizon:
            warn(
                ("The DeferrableLoad {} fill always run once in the op_horizon and not once in the lt_pattern\n" +
                 "If a different behaviour is intended, creating multiple DeferrableLoads should be considered")
                .format(self._long_ID)
            )

        self.P_Start_vars = []
        self.runtime = None

    def populate_model(self, model, mode="convex"):
        """Add variables and constraints to Gurobi model

        Call parent's `populate_model` method and set the upper bounds to the
        nominal power or zero depending on `self.time`. Also set a constraint
        for the minimum load. If mode == 'binary' add binary variables to model
        load as one block that can be shifted in time.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Uses integer variables to restrict the DL to operate
                           at nominal load or no load and restricts the DL to
                           consume E_Min_Consumption when DL is started without
                           returning to a no load state

        """
        super().populate_model(model, mode)
        if mode == "convex":
            if self.E_Consumption > self.op_horizon * self.time_slot * self.P_El_Nom:
                warn(
                    ("DeferrableLoad {} is not able to consume enough power in the op_horizon," +
                     "which will render the model infeasible")
                    .format(self._long_ID)
                )

            # consume E_Consumption the op_horizon
            model.addConstr(
                gurobi.quicksum(self.P_El_vars) * self.time_slot == self.E_Consumption
            )

        elif mode == "integer":
            self.runtime = self.E_Consumption / (self.P_El_Nom * self.time_slot)
            rounded_runtime = int(round(self.runtime))
            if not np.isclose(self.runtime, rounded_runtime):
                warn("Consumption of DLs is in integer mode always a multiple of " +
                     "P_El_Nom * dt, which is larger than E_Consumption")
            self.runtime = rounded_runtime

            if self.runtime > self.op_horizon:
                warn(
                    ("DeferrableLoad {} is not able to complete a run in the op_horizon, " +
                     "which will render the model infeasible")
                    .format(self._long_ID)
                )

            # create binary variables representing if operation begins in timeslot t
            # Since the DL has to finish operation when the op_horizon ends, binary variables representing a too late
            # start can be omitted.
            for t in self.op_time_vec[: -self.runtime + 1]:
                self.P_Start_vars.append(model.addVar(
                    vtype=gurobi.GRB.BINARY,
                    name="%s_Start_at_t=%i"
                         % (self._long_ID, t + 1)
                ))
            model.update()

            for t in self.op_time_vec:
                # coupling the start variable to the electrical variables following
                model.addConstr(
                    self.P_El_vars[t] == self.P_El_Nom * gurobi.quicksum(
                        self.P_Start_vars[max(0, t+1-self.runtime):t+1]
                    )
                )

            # run once in the op_horizon
            model.addConstr(
                gurobi.quicksum(self.P_Start_vars) == 1
            )
        else:
            raise ValueError(
                "Mode %s is not implemented by deferrable load." % str(mode)
            )

    def update_model(self, model, mode="convex"):
        if mode == "convex":
            load_time = self.load_time[self.op_slice]

            for t in self.op_time_vec:
                if load_time[t] == 1:
                    self.P_El_vars[t].ub = self.P_El_Nom
                else:
                    self.P_El_vars[t].ub = 0

        elif mode == "integer":
            if (self.load_time[self.timestep + self.op_horizon - 1] == 1 and
                    self.load_time[self.timestep + self.op_horizon] == 1):
                warn(
                    ("DeferrableLoad {} will not consider a start which would result in power consumption" +
                     "outside the op_horizon")
                    .format(self._long_ID)
                     )

            load_time = self.load_time[self.op_slice]

            for t, start_var in enumerate(self.P_Start_vars):
                if all(lt == 1 for lt in load_time[t:t+self.runtime]):
                    start_var.ub = 1
                else:
                    start_var.ub = 0

        else:
            raise ValueError(
                "Mode %s is not implemented by DL." % str(mode)
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
        optimal_P_El = self.E_Consumption / max_loading_time
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
