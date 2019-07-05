import gurobipy as gurobi

from pycity_scheduling.exception import NonoptimalError
from pycity_scheduling.util import populate_models


def local_optimization(city_district, models=None, robustness=None,
                       debug=True):
    """Implementation of the local optimization algorithm.

    Schedule all buildings in `city_district` on their own.

    Parameters
    ----------
    city_district : CityDistrict
    models : dict, optional
        Holds a single `gurobi.Model` for the whole district.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
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
        entity.update_model(model, robustness=robustness)
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
            import pycity_scheduling.util.debug as debug
            debug.analyze_model(model, e)
        raise NonoptimalError("Could not retrieve schedule from model.")
