"""
The pycity_scheduling framework


Copyright (C) 2020,
Institute for Automation of Complex Power Systems (ACS),
E.ON Energy Research Center (E.ON ERC),
RWTH Aachen University

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.classes import (CityDistrict, Building, Photovoltaic, WindEnergyConverter)
from pycity_scheduling.util import extract_pyomo_values, mpi_interface
from pycity_scheduling.algorithms.algorithm import IterationAlgorithm, DistributedAlgorithm, SolverNode
from pycity_scheduling.solvers import DEFAULT_SOLVER, DEFAULT_SOLVER_OPTIONS


class ExchangeADMMMPI(IterationAlgorithm, DistributedAlgorithm):
    """Implementation of the Exchange ADMM Algorithm.

    Uses the Exchange ADMM algorithm described in [1].

    Parameters
    ----------
    city_district : CityDistrict
    solver : str, optional
        Solver to use for solving (sub)problems.
    solver_options : dict, optional
        Options to pass to calls to the solver. Keys are the name of
        the functions being called and are one of `__call__`, `set_instance_`,
        `solve`.
        `__call__` is the function being called when generating an instance
        with the pyomo SolverFactory.  Additionally to the options provided,
        `node_ids` is passed to this call containing the IDs of the entities
        being optimized.
        `set_instance` is called when a pyomo Model is set as an instance of
        a persistent solver. `solve` is called to perform an optimization. If
        not set, `save_results` and `load_solutions` may be set to false to
        provide a speedup.
    mode : str, optional
        Specifies which set of constraints to use.
        - `convex`  : Use linear constraints
        - `integer`  : May use non-linear constraints
    eps_primal : float, optional
        Primal stopping criterion for the ADMM algorithm.
    eps_dual : float, optional
        Dual stopping criterion for the ADMM algorithm.
    rho : float, optional
        Stepsize for the ADMM algorithm.
    max_iterations : int, optional
        Maximum number of ADMM iterations.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.

    References
    ----------
    .. [1] "Alternating Direction Method of Multipliers for Decentralized
       Electric Vehicle Charging Control" by Jose Rivera, Philipp Wolfrum,
       Sandra Hirche, Christoph Goebel, and Hans-Arno Jacobsen
       Online: https://mediatum.ub.tum.de/doc/1187583/1187583.pdf (accessed on 2020/09/28)
    """
    def __init__(self, city_district, solver=DEFAULT_SOLVER, solver_options=DEFAULT_SOLVER_OPTIONS, mode="convex",
                 eps_primal=0.1, eps_dual=1.0, rho=2.0, max_iterations=10000, robustness=None):
        super(ExchangeADMMMPI, self).__init__(city_district, solver, solver_options, mode)

        self.mpi_interface = mpi_interface.MPI_Interface()

        self.eps_primal = eps_primal
        self.eps_dual = eps_dual
        self.rho = rho
        self.max_iterations = max_iterations
        # create solver nodes for each entity
        self.nodes = [
            SolverNode(solver, solver_options, [entity], mode, robustness=robustness)
            for entity in self.entities
        ]
        # create pyomo parameters for each entity
        for node, entity in zip(self.nodes, self.entities):
            node.model.beta = pyomo.Param(mutable=True, initialize=1)
            node.model.xs_ = pyomo.Param(entity.model.t, mutable=True, initialize=0)
            node.model.us = pyomo.Param(entity.model.t, mutable=True, initialize=0)
            node.model.last_p_el_schedules = pyomo.Param(entity.model.t, mutable=True, initialize=0)
        self._add_objective()

    def _add_objective(self):
        for i, node, entity in zip(range(len(self.entities)), self.nodes, self.entities):
            obj = node.model.beta * entity.get_objective()
            obj += self.rho / 2 * pyomo.sum_product(entity.model.p_el_vars, entity.model.p_el_vars)
            # penalty term is expanded and constant is omitted
            if i == 0:
                # invert sign of p_el_schedule and p_el_vars (omitted for quadratic
                # term)
                obj += self.rho * pyomo.sum_product(
                    [(-node.model.last_p_el_schedules[t] - node.model.xs_[t] - node.model.us[t])
                     for t in range(entity.op_horizon)],
                     entity.model.p_el_vars
                )
            else:
                obj += self.rho * pyomo.sum_product(
                    [(-node.model.last_p_el_schedules[t] + node.model.xs_[t] + node.model.us[t])
                     for t in range(entity.op_horizon)],
                    entity.model.p_el_vars
                )
            node.model.o = pyomo.Objective(expr=obj)
        return

    def _presolve(self, full_update, beta, robustness, debug):
        results, params = super()._presolve(full_update, beta, robustness, debug)

        for node, entity in zip(self.nodes, self.entities):
            node.model.beta = self._get_beta(params, entity)
            if full_update:
                node.full_update(robustness)
        results["r_norms"] = []
        results["s_norms"] = []
        return results, params

    def _is_last_iteration(self, results, params):
        return results["r_norms"][-1] <= self.eps_primal and results["s_norms"][-1] <= self.eps_dual

    def _iteration(self, results, params, debug):
        super(ExchangeADMMMPI, self)._iteration(results, params, debug)
        op_horizon = self.entities[0].op_horizon

        # fill parameters if not already present
        if "p_el" not in params:
            params["p_el"] = np.zeros((len(self.entities), op_horizon))
        if "x_" not in params:
            params["x_"] = np.zeros(op_horizon)
        if "u" not in params:
            params["u"] = np.zeros(op_horizon)
        u = params["u"]

        # -----------------
        # 1) optimize all entities
        # -----------------
        to_solve_nodes = []
        variables = []

        # Take actions if the number of MPI processes does not fit the total number of nodes:
        if self.mpi_interface.mpi_size > len(self.nodes):
            rank_id_range = np.array([i for i in range(len(self.nodes))])
            if self.mpi_interface.mpi_rank > len(self.nodes):
                results["r_norms"].append(0.0)
                results["s_norms"].append(0.0)
                return
        elif self.mpi_interface.mpi_size < len(self.nodes):
            if self.mpi_interface.mpi_size == 1:
                rank_id_range = np.array([0 for i in range(len(self.nodes))])
            else:
                a, b = divmod(len(self.nodes)-1, self.mpi_interface.mpi_size-1)
                rank_id_range = np.repeat(np.array([i for i in range(1, self.mpi_interface.mpi_size)]), a)
                for i in range(b):
                    rank_id_range = np.append(rank_id_range, i+1)
                rank_id_range = np.concatenate([[0], rank_id_range])
        else:
            rank_id_range = np.array([i for i in range(len(self.nodes))])
        rank_id_range = np.sort(rank_id_range)

        p_el_schedules = np.empty((len(self.entities), op_horizon))
        for i, node, entity in zip(range(len(self.nodes)), self.nodes, self.entities):
            if self.mpi_interface.mpi_rank == rank_id_range[i]:
                if not isinstance(
                        entity,
                        (CityDistrict, Building, Photovoltaic, WindEnergyConverter)
                ):
                    continue

                for t in range(op_horizon):
                    node.model.last_p_el_schedules[t] = params["p_el"][i][t]
                    node.model.xs_[t] = params["x_"][t]
                    node.model.us[t] = params["u"][t]
                node.obj_update()
                to_solve_nodes.append(node)
                variables.append([entity.model.p_el_vars[t] for t in range(op_horizon)])
        self._solve_nodes(results, params, to_solve_nodes, variables=variables, debug=debug)

        if self.mpi_interface.mpi_rank == 0:
            p_el_schedules[0] = np.array(extract_pyomo_values(self.entities[0].model.p_el_vars, float),
                                         dtype=np.float64)
        for j in range(1, len(self.nodes)):
            if not isinstance(
                    self.entities[j],
                    (CityDistrict, Building, Photovoltaic, WindEnergyConverter)
            ):
                continue

            if self.mpi_interface.mpi_rank == 0:
                if self.mpi_interface.mpi_size > 1:
                    data = np.empty(op_horizon, dtype=np.float64)
                    self.mpi_interface.mpi_comm.Recv(data, source=rank_id_range[j],
                                                     tag=int(results["iterations"][-1])*len(self.nodes)+j)
                    p_el_schedules[j] = np.array(data, dtype=np.float64)
                else:
                    p_el_schedules[j] = np.array(extract_pyomo_values(self.entities[j].model.p_el_vars, float),
                                                 dtype=np.float64)
            else:
                if self.mpi_interface.mpi_rank == rank_id_range[j]:
                    p_el_schedules[j] = np.array(extract_pyomo_values(self.entities[j].model.p_el_vars, float),
                                                 dtype=np.float64)
                    if self.mpi_interface.mpi_size > 1:
                        self.mpi_interface.mpi_comm.Send(p_el_schedules[j], dest=0,
                                                         tag=int(results["iterations"][-1])*len(self.nodes)+j)

        # --------------------------
        # 2) incentive signal update
        # --------------------------
        if self.mpi_interface.mpi_rank == 0:
            x_ = (-p_el_schedules[0] + sum(p_el_schedules[1:])) / len(self.entities)
            u += x_
            r_norm = np.array([np.math.sqrt(len(self.entities)) * np.linalg.norm(x_)], dtype=np.float64)
            s = np.zeros_like(p_el_schedules)
            s[0] = - self.rho * (-p_el_schedules[0] + params["p_el"][0] + params["x_"] - x_)
            for i in range(1, len(self.entities)):
                s[i] = - self.rho * (p_el_schedules[i] - params["p_el"][i] + params["x_"] - x_)
            s_norm = np.array([np.linalg.norm(s.flatten())], dtype=np.float64)
        else:
            x_ = np.empty(op_horizon, dtype=np.float64)
            u = np.empty(op_horizon, dtype=np.float64)
            r_norm = np.empty(1, dtype=np.float64)
            s_norm = np.empty(1, dtype=np.float64)
        if self.mpi_interface.mpi_size > 1:
            self.mpi_interface.mpi_comm.Bcast(x_, root=0)
            self.mpi_interface.mpi_comm.Bcast(u, root=0)
            self.mpi_interface.mpi_comm.Bcast(r_norm, root=0)
            self.mpi_interface.mpi_comm.Bcast(s_norm, root=0)

        # ------------------------------------------
        # 3) Calculate parameters for stopping criteria
        # ------------------------------------------
        results["r_norms"].append(r_norm[0])
        results["s_norms"].append(s_norm[0])

        # save parameters for another iteration
        params["p_el"] = p_el_schedules
        params["x_"] = x_
        params["u"] = u

        return
