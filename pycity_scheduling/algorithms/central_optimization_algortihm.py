import numpy as np
import pyomo.environ as pyomo
from pyomo.solvers.plugins.solvers.persistent_solver import PersistentSolver
from pyomo.opt import SolverStatus, TerminationCondition

from pycity_scheduling.exception import NonoptimalError
from pycity_scheduling.util import populate_models


def central_optimization(city_district, optimizer="gurobi_persistent", mode="convex", models=None, beta=1, robustness=None,
                         debug=True):
    """Implementation of the central optimization algorithm.

    Schedule all buildings together with respect to the aggregator objective.
    Result should be the same as the one from Exchange ADMM. Though this
    algorithm only uses one big Gurobi models, which might be problematic in
    terms of scalability or data privacy.

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
        Holds a single `pyomo.ConcreteModel` for the whole district.
    beta : float, optional
        Tradeoff factor between system and customer objective. The customer
        objective is multiplied with beta.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    debug : bool, optional
        Specify wether detailed debug information shall be printed.
    """

    optimizer = pyomo.SolverFactory(optimizer)
    nodes = city_district.node

    if models is None:
        models = populate_models(city_district, mode, 'central', robustness)
    model = models[0]
    city_district.update_model(mode)

    obj = city_district.get_objective()
    for node_id, node in nodes.items():
        entity = node['entity']
        entity.update_model(mode, robustness=robustness)
        obj += entity.get_objective(beta)
    model.o = pyomo.Objective(expr=obj)

    if isinstance(optimizer, PersistentSolver):
        optimizer.set_instance(model)
        result = optimizer.solve()
    else:
        result = optimizer.solve(model)
    if result.solver.termination_condition != TerminationCondition.optimal or result.solver.status != SolverStatus.ok:
        if debug:
            import pycity_scheduling.util.debug as debug
            debug.analyze_model(model, optimizer, result)
        raise NonoptimalError("Could not retrieve schedule from model.")
    for node in city_district.node.values():
        entity = node['entity']
        entity.update_schedule()
    city_district.update_schedule()
