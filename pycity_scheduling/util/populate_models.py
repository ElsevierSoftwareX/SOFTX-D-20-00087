import gurobipy as gurobi


def populate_models(city_district, algorithm, num_threads=4):
    """Populate models for scheduling.

    Creates Gurobi models for scheduling. One model for reference, local and
    central scheduling and multiple models (one for each node and one for the
    aggregator) for Exchange ADMM.

    Parameters
    ----------
    city_district : CityDistrict
    algorithm : str
        Define which algorithm the models are used for. Must be one of "admm",
        "stand-alone", "local", "central" or "dual-decompostition".
    num_threads : int, optional
        Number of threads for the gurobi optimization.

    Returns
    -------
    dict :
        Holds one or more `gurobi.Model`.
    """
    op_horizon = city_district.op_horizon
    op_time_vec = city_district.op_time_vec
    nodes = city_district.node

    # create dictionary
    models = {}
    if algorithm in ["stand-alone", "local", "central"]:
        m = gurobi.Model("central_algorithm_model")
        m.setParam("OutputFlag", False)
        m.setParam("LogFile", "")
        m.setParam("Threads", num_threads)
        P_El_var_list = []
        for node in nodes.values():
            entity = node['entity']
            entity.populate_model(m)
            P_El_var_list.extend(entity.P_El_vars)
        city_district.populate_model(m)
        for t in op_time_vec:
            P_El_var_sum = gurobi.quicksum(P_El_var_list[t::op_horizon])
            m.addConstr(city_district.P_El_vars[t] == P_El_var_sum)
        models[0] = m
    elif algorithm in ["admm", "dual-decomposition"]:
        m = gurobi.Model("Aggregator Scheduling Model")
        m.setParam("OutputFlag", False)
        m.setParam("LogFile", "")
        m.setParam("Threads", num_threads)
        city_district.populate_model(m)
        models[0] = m
        for node_id, node in nodes.items():
            m = gurobi.Model(str(node_id) + " Scheduling Model")
            m.setParam("OutputFlag", False)
            m.setParam("LogFile", "")
            m.setParam("Threads", num_threads)
            node['entity'].populate_model(m)
            models[node_id] = m
    return models
