"""
The pycity_scheduling framework


Copyright (C) 2022,
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
from pycity_scheduling.util import extract_pyomo_values
from pycity_scheduling.algorithms.algorithm import IterationAlgorithm, DistributedAlgorithm, SolverNode
from pycity_scheduling.solvers import DEFAULT_SOLVER, DEFAULT_SOLVER_OPTIONS


class DualDecomposition(IterationAlgorithm, DistributedAlgorithm):
    """Implementation of the Dual Decomposition Algorithm.

    """
    def __init__(self, city_district, solver=DEFAULT_SOLVER, solver_options=DEFAULT_SOLVER_OPTIONS, mode="convex",
                 eps_primal=0.1, rho=2.0, max_iterations=10000, robustness=None):
        """
        Set up the Dual Decomposition Algorithm for optimizing a specific city district.

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
            Primal stopping criterion for the dual decomposition algorithm.
        rho : float, optional
            Stepsize for the dual decomposition algorithm.
        max_iterations : int, optional
            Maximum number of ADMM iterations.
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        """
        super(DualDecomposition, self).__init__(city_district, solver, solver_options, mode)
        self.eps_primal = eps_primal
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
            node.model.lambdas = pyomo.Param(entity.model.t, mutable=True, initialize=0)
        self._add_objective()

    def _add_objective(self):
        for i, node, entity in zip(range(len(self.entities)), self.nodes, self.entities):
            obj = node.model.beta * entity.get_objective()
            if i == 0:
                # penalty term is expanded and constant is omitted
                # invert sign of p_el_schedule and p_el_vars (omitted for quadratic
                # term)
                obj -= pyomo.sum_product(node.model.lambdas, entity.model.p_el_vars)
            else:
                obj += pyomo.sum_product(node.model.lambdas, entity.model.p_el_vars)
            node.model.o = pyomo.Objective(expr=obj)
        return

    def _presolve(self, full_update, beta, robustness, debug):
        results, params = super()._presolve(full_update, beta, robustness, debug)

        for node, entity in zip(self.nodes, self.entities):
            node.model.beta = self._get_beta(params, entity)
            if full_update:
                node.full_update(robustness)
        results["r_norms"] = []
        results["lambdas"] = []
        return results, params

    def _is_last_iteration(self, results, params):
        return results["r_norms"][-1] <= self.eps_primal

    def _iteration(self, results, params, debug):
        super(DualDecomposition, self)._iteration(results, params, debug)
        op_horizon = self.entities[0].op_horizon
        if "lambdas" not in params:
            params["lambdas"] = np.zeros(op_horizon)
        lambdas = params["lambdas"]

        # -----------------
        # 1) optimize all entities
        # -----------------
        for i, node, entity in zip(range(len(self.nodes)), self.nodes, self.entities):
            if not isinstance(
                    entity,
                    (CityDistrict, Building, Photovoltaic, WindEnergyConverter)
            ):
                continue
            for t in range(op_horizon):
                node.model.lambdas[t] = lambdas[t]
            node.obj_update()
            node.solve(variables=[entity.model.p_el_vars[t] for t in range(op_horizon)], debug=debug)

        # --------------------------
        # 2) incentive signal update
        # --------------------------
        p_el_schedules = np.array([extract_pyomo_values(entity.model.p_el_vars, float) for entity in self.entities])
        lambdas -= self.rho * p_el_schedules[0]
        lambdas += self.rho * np.sum(p_el_schedules[1:], axis=0)

        # ------------------------------------------
        # 3) Calculate parameters for stopping criteria
        # ------------------------------------------
        r = np.zeros(op_horizon)
        r -= p_el_schedules[0]
        r += np.sum(p_el_schedules[1:], axis=0)

        # save parameters for another iteration
        results["r_norms"].append(np.linalg.norm(r, np.inf))
        results["lambdas"].append(np.copy(lambdas))
        return
