import gurobipy as gurobi

from pycity_scheduling import util
from pycity_scheduling.exception import NonoptimalError
from pycity_scheduling.util import populate_models


def local_optimization(city_district, models=None, debug=True):
    """Implementation of the local optimization algorithm.

    Schedule all buildings in `city_district` on their own.

    Parameters
    ----------
    city_district : CityDistrict
    models : dict, optional
        Holds a single `gurobi.Model` for the whole district.
    debug : bool, optional
        Specify wether detailed debug information shall be printed.
    """

    nodes = city_district.node

    if models is None:
        models = populate_models(city_district, 'local')
    model = models[0]
    city_district.update_model(model)

    obj = gurobi.QuadExpr()
    for node_id, node in nodes.items():
        entity = node['entity']
        entity.update_model(model)
        obj.add(entity.get_objective())
    model.setObjective(obj)

    model.optimize()
    try:
        for node in city_district.node.values():
            entity = node['entity']
            entity.update_schedule()
        city_district.update_schedule()
    except Exception as e:
        if debug:
            util.analyze_model(model, e)
        raise NonoptimalError("Could not retrieve schedule from model.")
