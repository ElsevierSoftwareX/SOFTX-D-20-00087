"""
The pycity_scheduling framework


@institution:
Institute for Automation of Complex Power Systems (ACS)
E.ON Energy Research Center
RWTH Aachen University

@author:
Sebastian Schwarz, M.Sc.
Sebastian Alexander Uerlich, B.Sc.
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo
from warnings import warn
import pycity_base.classes.demand.electrical_demand as ed

from pycity_scheduling.classes.electrical_entity import ElectricalEntity
from pycity_scheduling import util


class DeferrableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pyCity_base class ElectricalDemand for scheduling purposes.

    The Load will always run once in the op_horizon

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    p_el_nom : float
        Nominal electric power in [kW].
    e_consumption : float
         Power to be consumed over the op_horizon in [kWh].
    load_time : array of binaries, optional
        Indicator when deferrable load can be turned on. Defaults to always.
        `load_time[t] == 0`: device is off in t
        `load_time[t] == 1`: device can be turned on in t
        It must contain at least one `0` otherwise the model will become
        infeasible. Its length has to be consistent with `lt_pattern`.
    lt_pattern : str, optional
        Define how the `load_time` profile is to be used

        - `None` : Profile matches simulation horizon.
        - 'daily' : Profile matches one day.
        - 'weekly' : Profile matches one week.

    Raises
    ------
    ValueError :
        If `lt_pattern` does not match `load_time`.

    Notes
    -----
    DLs offer sets of constraints for operation. In the `convex` mode the following
    constraints and bounds are generated by the DL:

    .. math::
        p_{el\\_nom} \\geq p_{el\\_i} \\geq 0, & \\quad \\text{if} \\quad lt\\_pattern_i = 1  \\\\
        p_{el\\_i} = 0, & \\quad \\text{else}

    .. math::
        \\sum_i p_{el\\_i} * \\Delta t = e_{consumption}

    The constraints are replaced in integer mode with the following constraints:

    .. math::
        \\sum_i p_{state\\_i} &=& 1 \\\\
        runtime &=& \\lfloor \\frac{p_{el\\_nom} * \\Delta t}{e_{consumption}} \\rceil \\\\
        p_{el\\_i} &=& p_{el\\_nom} * \\sum_{j=i-runtime+1}^{i} p_{state\\_j} \\\\
        p_{state\\_i} &=& 0, \\quad \\text{if} \\quad \\sum_{j=i}^{i+runtime-1}
        lt\\_pattern_j = runtime \\\\

    These constraints do not take the previous values before the current optimization
    horizon into account. In the optimization horizon :math:`e_{consumption}` always
    has to be consumed.
    """

    def __init__(self, environment, p_el_nom, e_consumption, load_time=None, lt_pattern=None):
        shape = environment.timer.timesteps_total
        super().__init__(environment, 0, np.zeros(shape))

        self._long_ID = "DL_" + self._ID_string

        self.p_el_nom = p_el_nom
        self.e_consumption = e_consumption
        if load_time is None:
            lt_pattern = None
            load_time = np.ones(self.simu_horizon)
        self.load_time = util.compute_profile(self.timer, load_time, lt_pattern)

        if len(load_time) != self.op_horizon:
            warn(
                ("The DeferrableLoad {} will always run once in the op_horizon and not once in the lt_pattern.\n" +
                 "If a different behaviour is intended, initializing multiple DeferrableLoads should be considered.")
                .format(self._long_ID)
            )

        self.new_var("p_start", dtype=np.bool, func=self._get_start)

        self.runtime = int(round(self.e_consumption / (self.p_el_nom * self.time_slot)))

    def _get_start(self, model):
        cumsum = np.cumsum(self.schedule["p_el"][self.op_slice])
        runtime_consumptions = cumsum[self.runtime:] - cumsum[:-self.runtime]
        starts = np.zeros(self.op_horizon, dtype=np.bool)
        starts[np.argmax(runtime_consumptions)] = True
        return starts

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method and set the upper bounds to the
        nominal power or zero depending on `self.load_time`. Also set a constraint
        for the minimum load. If mode == `integer` add binary variables to model
        load as one block that can be shifted in time.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Uses integer variables to restrict the DL to operate
               at nominal load or no load and restricts the DL to consume
               E_Min_Consumption when DL is started without returning to a no
               load state

        """
        super().populate_model(model, mode)
        m = self.model
        if mode == "convex":
            if self.e_consumption > self.op_horizon * self.time_slot * self.p_el_nom:
                warn(
                    ("DeferrableLoad {} is not able to consume enough power in the given op_horizon," +
                     "which will render the model infeasible")
                    .format(self._long_ID)
                )

            # consume e_consumption the op_horizon
            def p_consumption_rule(model):
                return pyomo.sum_product(model.p_el_vars) * self.time_slot == self.e_consumption
            m.P_consumption_constr = pyomo.Constraint(rule=p_consumption_rule)

        elif mode == "integer":
            self.runtime = self.e_consumption / (self.p_el_nom * self.time_slot)
            rounded_runtime = int(round(self.runtime))
            if not np.isclose(self.runtime, rounded_runtime):
                warn("Consumption of DLs is in integer mode always a multiple of " +
                     "p_el_nom * dt, which is larger than e_consumption.")
            self.runtime = rounded_runtime

            if self.runtime > self.op_horizon:
                warn(
                    ("DeferrableLoad {} is not able to complete its operation in the given op_horizon, " +
                     "which will render the model infeasible.")
                    .format(self._long_ID)
                )

            # create binary variables representing if operation begins in timeslot t
            # Since the DL has to finish operation when the op_horizon ends, binary variables representing a too late
            # start can be omitted.
            m.p_start_vars = pyomo.Var(pyomo.RangeSet(0, self.op_horizon-self.runtime), domain=pyomo.Binary)

            # coupling the start variable to the electrical variables following
            def state_coupl_rule(model, t):
                return model.p_el_vars[t] == self.p_el_nom * pyomo.quicksum(
                       (model.p_start_vars[t] for t in range(max(0, t+1-self.runtime),
                                                             min(self.op_horizon-self.runtime+1, t+1))))
            m.state_coupl_integer_constr = pyomo.Constraint(m.t, rule=state_coupl_rule)

            # run once in the op_horizon
            def state_once_rule(model):
                return pyomo.sum_product(model.p_start_vars) == 1.0
            m.state_once_integer_constr = pyomo.Constraint(rule=state_once_rule)

        else:
            raise ValueError(
                "Mode %s is not implemented by class DeferrableLoad." % str(mode)
            )
        return

    def update_model(self, mode="convex"):
        m = self.model
        if mode == "convex":
            load_time = self.load_time[self.op_slice]

            for t in self.op_time_vec:
                if load_time[t] == 1:
                    m.p_el_vars[t].setub(self.p_el_nom)
                else:
                    m.p_el_vars[t].setub(0.0)

        elif mode == "integer":
            if (self.timestep + self.op_horizon < self.simu_horizon and
                    self.load_time[self.timestep + self.op_horizon - 1] == 1 and
                    self.load_time[self.timestep + self.op_horizon] == 1):
                warn(
                    ("DeferrableLoad {} will not consider a start which would result in power consumption" +
                     "outside the op_horizon")
                    .format(self._long_ID)
                     )

            load_time = self.load_time[self.op_slice]

            for t, start_var in m.p_start_vars.items():
                if all(lt == 1 for lt in load_time[t:t+self.runtime]):
                    start_var.setub(1.0)
                else:
                    start_var.setub(0.0)

        else:
            raise ValueError(
                "Mode %s is not implemented by DL." % str(mode)
            )
        return

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the deferrable load weighted with
        coeff. Quadratic term minimizing the deviation from the optimal
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
        max_loading_time = sum(self.load_time) * self.time_slot
        optimal_p_el = self.e_consumption / max_loading_time
        obj = coeff * pyomo.sum_product(m.p_el_vars, m.p_el_vars)
        obj += -2 * coeff * optimal_p_el * pyomo.sum_product(m.p_el_vars)
        return obj
