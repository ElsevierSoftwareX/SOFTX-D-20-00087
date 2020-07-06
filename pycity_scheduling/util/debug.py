import pyomo.environ as pyomo
from pyomo.opt import SolverStatus, TerminationCondition
from pyomo.solvers.plugins.solvers.direct_or_persistent_solver import DirectOrPersistentSolver
from pyomo.opt.results.results_ import SolverResults
import pyomo.solvers.plugins.solvers as Solvers


def analyze_model(model, optimizer, result, options={}):
    """Analyze a model which is not optimal.

    Parameters
    ----------
    model : pyomo.ConcreteModel
        Model with `status != GRB.OPTIAML`
    optimizer : DirectOrPersistentSolver
        The solver that was used for optimization and is used for analyzes
    result: SolverResults
        The not optimal result that was returned by the solver
    options : str, optional
        Options which should be passed to the solver when analyzing
    """
    if result.solver.termination_condition in \
            [TerminationCondition.infeasibleOrUnbounded, TerminationCondition.infeasible] and \
            (isinstance(optimizer, Solvers.GUROBI.GUROBI)
             or isinstance(optimizer, Solvers.gurobi_persistent.GurobiPersistent)
             or isinstance(optimizer, Solvers.gurobi_direct.GurobiDirect) \
             or isinstance(optimizer, Solvers.GUROBI.GUROBISHELL)):

        options["dualreductions"] = 0
        if isinstance(optimizer, Solvers.gurobi_persistent.GurobiPersistent):
            optimizer.set_instance(model, symbolic_solver_labels=True)
            result = optimizer.solve(options=options, tee=True)
            if result.solver.termination_condition == TerminationCondition.infeasible:
                options["ResultFile"] = "model.ilp"
                optimizer.solve(options=options, tee=True)
                print("IIS written to 'model.ilp'.")
        else:
            result = optimizer.solve(model, options=options, tee=True, symbolic_solver_labels=True)
            if result.solver.termination_condition == TerminationCondition.infeasible:
                options["ResultFile"] = "model.ilp"
                optimizer.solve(model, options=options, tee=True, symbolic_solver_labels=True)
                print("IIS written to 'model.ilp'.")
    status = result.solver.status
    condition = result.solver.termination_condition
    print("Model status is {}.".format(status))
    print("Model condition is {}.".format(condition))


def print_district(cd, lvl=1):
    """Hierarchically print a city district.

    Parameters
    ----------
    cd : pycity_scheduling.classes.CityDistrict
    lvl : int, optional
        - `0` : Only print city district.
        - `1` : Only print city district and buildings.
        - `2` : Print city district, buildings and all their devices.
    """
    print(cd)
    if lvl < 1:
        return
    for bd in cd.get_lower_entities():
        print("\t{}".format(bd))
        if lvl < 2:
            continue
        if bd.hasBes:
            for e in bd.bes.get_lower_entities():
                print("\t\t{}".format(e))
        if len(bd.apartments) == 1:
            for e in bd.apartments[0].get_lower_entities():
                print("\t\t{}".format(e))
        elif len(bd.apartments) > 1:
            for ap in bd.apartments:
                print("\t\t{}".format(ap))
                for e in ap.get_lower_entities():
                    print("\t\t\t{}".format(e))
