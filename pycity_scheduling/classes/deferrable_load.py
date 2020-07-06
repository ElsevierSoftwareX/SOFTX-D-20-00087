import numpy as np
import pyomo.environ as pyomo
from pyomo.core.expr.numeric_expr import ExpressionBase
import pycity_base.classes.demand.ElectricalDemand as ed

from warnings import warn
from .electrical_entity import ElectricalEntity
from pycity_scheduling import util


class DeferrableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pyCity_base class ElectricalDemand for scheduling purposes.
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
                ("The DeferrableLoad {} will always run once in the op_horizon and not once in the lt_pattern\n" +
                 "If a different behaviour is intended, creating multiple DeferrableLoads should be considered")
                .format(self._long_ID)
            )

        self.new_var("P_Start", dtype=np.bool, func=lambda model, t:
                     t == np.argmax(np.array(
                         [sum(pyomo.value(model.P_El_vars[i])
                          for i in range(start, start+self.runtime))
                          for start in range(0, self.op_horizon - self.runtime)
                          ])
                     ))

        self.runtime = int(round(self.E_Consumption / (self.P_El_Nom * self.time_slot)))

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method and set the upper bounds to the
        nominal power or zero depending on `self.time`. Also set a constraint
        for the minimum load. If mode == 'binary' add binary variables to model
        load as one block that can be shifted in time.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Uses integer variables to restrict the DL to operate
                           at nominal load or no load and restricts the DL to
                           consume E_Min_Consumption when DL is started without
                           returning to a no load state

        """
        super().populate_model(model, mode)
        m = self.model
        if mode == "convex":
            if self.E_Consumption > self.op_horizon * self.time_slot * self.P_El_Nom:
                warn(
                    ("DeferrableLoad {} is not able to consume enough power in the op_horizon," +
                     "which will render the model infeasible")
                    .format(self._long_ID)
                )

            # consume E_Consumption the op_horizon
            def p_consumption_rule(model):
                return pyomo.sum_product(model.P_El_vars) * self.time_slot == self.E_Consumption
            m.P_consumption_constr = pyomo.Constraint(rule=p_consumption_rule)

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
            m.P_Start_vars = pyomo.Var(pyomo.RangeSet(0, self.op_horizon-self.runtime), domain=pyomo.Binary)

            # coupling the start variable to the electrical variables following
            def state_coupl_rule(model, t):
                return model.P_El_vars[t] == self.P_El_Nom * pyomo.quicksum(
                       (model.P_Start_vars[t] for t in range(max(0, t+1-self.runtime),
                                                             min(self.op_horizon-self.runtime+1, t+1))))
            m.state_coupl_constr = pyomo.Constraint(m.t, rule=state_coupl_rule)

            # run once in the op_horizon
            def state_once_rule(model):
                return 1 == pyomo.sum_product(model.P_Start_vars)
            m.state_once_constr = pyomo.Constraint(rule=state_once_rule)

        else:
            raise ValueError(
                "Mode %s is not implemented by deferrable load." % str(mode)
            )

    def update_model(self, mode="convex"):
        m = self.model
        if mode == "convex":
            load_time = self.load_time[self.op_slice]

            for t in self.op_time_vec:
                if load_time[t] == 1:
                    m.P_El_vars[t].setub(self.P_El_Nom)
                else:
                    m.P_El_vars[t].setub(0)

        elif mode == "integer":
            if (self.load_time[self.timestep + self.op_horizon - 1] == 1 and
                    self.load_time[self.timestep + self.op_horizon] == 1):
                warn(
                    ("DeferrableLoad {} will not consider a start which would result in power consumption" +
                     "outside the op_horizon")
                    .format(self._long_ID)
                     )

            load_time = self.load_time[self.op_slice]

            for t, start_var in m.P_Start_vars.items():
                if all(lt == 1 for lt in load_time[t:t+self.runtime]):
                    start_var.setub(1)
                else:
                    start_var.setub(0)

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
        ExpressionBase :
            Objective function.
        """
        m = self.model
        max_loading_time = sum(self.time) * self.time_slot
        optimal_P_El = self.E_Consumption / max_loading_time
        obj = coeff * pyomo.sum_product(m.P_El_vars, m.P_El_vars)
        obj += -2 * coeff * optimal_P_El * pyomo.sum_product(m.P_El_vars)
        return obj
