import gurobi

from pycity_scheduling.util import populate_models


def central_optimization(city_district, models=None, beta=1):
    """Implementation of the central optimization algorithm.

    Schedule all buildings together with respect to the aggregator objective.
    Result should be the same as the one from Exchange ADMM. Though this
    algorithm only uses one big Gurobi models, which might be problematic in
    terms of scalability or data privacy.

    Parameters
    ----------
    city_district : CityDistrict
    models : dict, optional
        Holds a single `gurobi.Model` for the whole district.
    beta : float, optional
        Tradeoff factor between system and customer objective. The customer
        objective is multiplied with beta.
    """

    nodes = city_district.node

    if models is None:
        models = populate_models(city_district, "central")
    model = models[0]
    city_district.update_model(model)

    obj = gurobi.QuadExpr()
    for node_id, node in nodes.items():
        entity = node['entity']
        entity.update_model(model)
        obj.add(entity.get_objective(beta))
    obj.add(city_district.get_objective())
    model.setObjective(obj)

    model.optimize()

    for node in city_district.node.values():
        entity = node['entity']
        entity.update_schedule()
    city_district.update_schedule()
