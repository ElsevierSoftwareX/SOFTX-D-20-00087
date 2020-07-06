import numpy as np
import pyomo.environ as pyomo
from pyomo.solvers.plugins.solvers.persistent_solver import PersistentSolver
from pyomo.opt import SolverStatus, TerminationCondition

from pycity_scheduling.classes import (Building, Photovoltaic,
                                       WindEnergyConverter)
from pycity_scheduling.exception import (MaxIterationError, NonoptimalError)
from pycity_scheduling.util import populate_models


def dual_decomposition(city_district, optimizer="gurobi_persistent", mode="convex", models=None, eps_primal=0.01,
                       rho=0.01, max_iterations=10000, robustness=None, debug=True):
    """Implementation of the Dual Decomposition Algorithm.

    Parameters
    ----------
    city_district : CityDistrict
    optimizer : str
        Solver to use for solving (sub)problems
    mode : str, optional
        Specifies which set of constraints to use
        - `convex`  : Use linear constraints
        - `integer`  : May use non-linear constraints
    models : dict, optional
        Holds a `pyomo.ConcreteModel` for each node and the aggregator.
    eps_primal : float, optional
        Primal stopping criterion for the dual decomposition algorithm.
    rho : float, optional
        Stepsize for the dual decomposition algorithm.
    max_iterations : int, optional
        Maximum number of ADMM iterations.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    debug : bool, optional
        Specify wether detailed debug information shall be printed.
    """

    OP_HORIZON = city_district.op_horizon
    nodes = city_district.nodes

    iteration = 0
    lambdas = np.zeros(OP_HORIZON)
    r_norms = [np.inf]


    if models is None:
        models = populate_models(city_district, mode, 'dual-decomposition', robustness)

        # hack to suppress pyomo no constraint warning
        models[0].simple_var = pyomo.Var(domain=pyomo.Reals, bounds=(None, None), initialize=0)
        models[0].simple_constr = pyomo.Constraint(expr=models[0].simple_var == 1)

    for node_id, node in nodes.items():
        node['entity'].update_model(mode, robustness=robustness)

    city_district.update_model(mode)

    # prepare solver if persistent
    optimizers = {0: pyomo.SolverFactory(optimizer)}
    persistent = isinstance(optimizers[0], PersistentSolver)
    if persistent:
        optimizers[0].set_instance(models[0])
        for node_id, node in nodes.items():
            optimizers[node_id] = pyomo.SolverFactory(optimizer)
            optimizers[node_id].set_instance(models[node_id])
    else:
        for node_id in nodes.keys():
            optimizers[node_id] = optimizers[0]

    # ----------------
    # Start scheduling
    # ----------------

    # do optimization iterations until stopping criteria are met
    while (r_norms[-1]) > eps_primal:
        iteration += 1
        if iteration > max_iterations:
            if debug:
                print(
                    "Exceeded iteration limit of {0} iterations. "
                    "Norm is ||r|| =  {1}.".format(max_iterations, r_norms[-1])
                )
            raise MaxIterationError("Iteration Limit exceeded.")

        # -----------------
        # 1) optimize nodes
        # -----------------
        for node_id, node in nodes.items():
            entity = node['entity']
            if not isinstance(
                    entity,
                    (Building, Photovoltaic, WindEnergyConverter)
            ):
                continue

            obj = entity.get_objective()
            # penalty term is expanded
            obj += pyomo.sum_product(lambdas, entity.model.P_El_vars)
            obj = pyomo.Objective(expr=obj)

            model = models[node_id]
            if hasattr(model, "o"):
                model.del_component("o")
            model.add_component("o", obj)

            if persistent:
                optimizers[node_id].set_objective(model.o)
                result = optimizers[node_id].solve()
            else:
                result = optimizers[node_id].solve(model)
            if result.solver.termination_condition != TerminationCondition.optimal or result.solver.status != SolverStatus.ok:
                if debug:
                    import pycity_scheduling.util.debug as debug
                    debug.analyze_model(model, optimizers[node_id], result)
                raise NonoptimalError("Could not retrieve schedule from model.")
            entity.update_schedule()

        # ----------------------
        # 2) optimize aggregator
        # ----------------------
        model = models[0]

        obj = city_district.get_objective()
        # penalty term is expanded and constant is omitted
        # invert sign of P_El_Schedule and P_El_vars (omitted for quadratic
        # term)
        obj += pyomo.sum_product(-lambdas, city_district.model.P_El_vars)
        obj = pyomo.Objective(expr=obj)

        if hasattr(model, "o"):
            model.del_component("o")
        model.add_component("o", obj)

        if persistent:
            optimizers[0].set_objective(model.o)
            result = optimizers[0].solve()
        else:
            result = optimizers[0].solve(model)
        if result.solver.termination_condition != TerminationCondition.optimal or result.solver.status != SolverStatus.ok:
            if debug:
                import pycity_scheduling.util.debug as debug
                debug.analyze_model(model, optimizers[0], result)
            raise NonoptimalError("Could not retrieve schedule from model.")
        city_district.update_schedule()

        # ----------------------
        # 3) Incentive Update
        # ----------------------

        t1 = city_district.timer.currentTimestep
        t2 = t1 + OP_HORIZON
        lambdas -= rho * city_district.P_El_Schedule[t1:t2]
        for node in nodes.values():
            lambdas += rho * node['entity'].P_El_Schedule[t1:t2]

        # ------------------------------------------
        # Calculate parameters for stopping criteria
        # ------------------------------------------

        r_norms.append(0)
        r = np.zeros(OP_HORIZON)
        np.copyto(r, -city_district.P_El_Schedule[t1:t2])
        for node in nodes.values():
            r += node["entity"].P_El_Schedule[t1:t2]

        for t in city_district.op_time_vec:
            if abs(r[t]) > r_norms[-1]:
                r_norms[-1] = abs(r[t])

    return iteration, r_norms, lambdas
