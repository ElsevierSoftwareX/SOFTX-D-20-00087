import gurobipy as gurobi


_status_codes = [
    'LOADED',
    'OPTIMAL',
    'INFEASIBLE',
    'INF_OR_UNBD',
    'UNBOUNDED',
    'CUTOFF',
    'ITERATION_LIMIT',
    'NODE_LIMIT',
    'TIME_LIMIT',
    'SOLUTION_LIMIT',
    'INTERRUPTED',
    'NUMERIC',
    'SUBOPTIMAL',
    'INPROGRESS',
    'USER_OBJ_LIMIT',
]

status_codes_map = {eval(c, {}, gurobi.GRB.__dict__): c for c in _status_codes}


def analyze_model(model, exception=None):
    """Analyze a Gurobi model which is not optimal.

    Parameters
    ----------
    model : gurobipy.Model
        Model with `status != GRB.OPTIAML`
    exception : Exception, optional
        Original exception, whose message will be printed
    """
    model.setParam('OutputFlag', True)
    if model.status == gurobi.GRB.INF_OR_UNBD:
        model.setParam('dualreductions', 0)
        model.optimize()
    status = model.status
    print("Model status is {}.".format(status_codes_map[status]))
    if exception:
        print("Original Error:")
        print(exception)
    if status == gurobi.GRB.INFEASIBLE:
        model.computeIIS()
        model.write('model.ilp')
        print("IIS written to 'model.ilp'.")


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
