import numpy as np
import gurobipy as gurobi

from pycity_scheduling.classes import *
from pycity_scheduling.exception import *
from pycity_scheduling.util import populate_models


def dual_decomposition(city_district, models=None, eps_primal=0.01,
                       rho=0.01, max_iterations=10000):
    """Implementation of the Dual Decomposition Algorithm.

    Parameters
    ----------
    city_district : CityDistrict
    models : dict, optional
        Holds a `gurobi.Model` for each node and the aggregator.
    eps_primal : float, optional
        Primal stopping criterion for the dual decomposition algorithm.
    rho : float, optional
        Stepsize for the dual decomposition algorithm.
    max_iterations : int, optional
        Maximum number of ADMM iterations.
    """

    OP_HORIZON = city_district.op_horizon
    nodes = city_district.nodes

    iteration = 0
    lambdas = np.zeros(OP_HORIZON)
    r_norms = [gurobi.GRB.INFINITY]

    runtimes = {node_id: list() for node_id in nodes.keys()}
    runtimes[0] = list()

    if models is None:
        models = populate_models(city_district, "dual-decomposition")

    for node_id, node in nodes.items():
        node['entity'].update_model(models[node_id])

    city_district.update_model(models[0])

    # ----------------
    # Start scheduling
    # ----------------

    # do optimization iterations until stopping criteria are met
    while (r_norms[-1]) > eps_primal:
        iteration += 1
        if iteration > max_iterations:
            raise PyCitySchedulingMaxIteration(
                "Exceeded iteration limit of {0} iterations\n"
                "Norms were ||r|| =  {1}"
                .format(max_iterations, r_norms[-1])
            )

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
            obj.addTerms(
                lambdas,
                entity.P_El_vars
            )

            model = models[node_id]
            model.setObjective(obj)
            model.optimize()
            runtimes[node_id].append(model.Runtime)
            try:
                entity.update_schedule()
            except PyCitySchedulingGurobiException as e:
                print(e.args)
                print("Model Status: %i" % model.status)
                if model.status == 4:
                    model.computeIIS()
                    model.write("infeasible.ilp")
                raise

        # ----------------------
        # 2) optimize aggregator
        # ----------------------
        model = models[0]

        obj = city_district.get_objective()
        # penalty term is expanded and constant is omitted
        # invert sign of P_El_Schedule and P_El_vars (omitted for quadratic
        # term)
        obj.addTerms(
            -lambdas,
            city_district.P_El_vars
        )

        model.setObjective(obj)
        model.optimize()
        runtimes[0].append(model.Runtime)
        try:
            city_district.update_schedule()
        except PyCitySchedulingGurobiException:
            print(model.status)
            raise

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
