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

from pycity_scheduling.algorithms.algorithm import DistributedAlgorithm, SolverNode
from pycity_scheduling.solvers import DEFAULT_SOLVER, DEFAULT_SOLVER_OPTIONS


class LocalOptimization(DistributedAlgorithm):
    """Implementation of the reference optimization algorithm.

        Schedule all nodes in `city_district` on their own.
    """
    def __init__(self, city_district, solver=DEFAULT_SOLVER, solver_options=DEFAULT_SOLVER_OPTIONS, mode="convex",
                 robustness=None):
        super(LocalOptimization, self).__init__(city_district, solver, solver_options, mode)
        # create solver nodes for each entity
        self.nodes = [
            SolverNode(solver, solver_options, [entity], mode, robustness=robustness)
            for entity in self.entities
        ]
        # create coupling for city district model only
        self._add_coupling(self.nodes[0].model)
        # create pyomo parameters for beta of each entity
        for node in self.nodes:
            node.model.beta = pyomo.Param(mutable=True, initialize=1)
        self._add_objective()

    def _add_coupling(self, model):
        """Adds the coupling constraint to the model.

        This constraint 'connects' the district operator to all its nodes.

        Parameters
        ----------
        model : pyomo.ConcreteModel
            Model to add the constraint to.
        """
        model.cd_consumption = pyomo.Param(self.city_district.model.t, mutable=True)

        def p_el_couple_rule(model, t):
            return self.city_district.model.p_el_vars[t] == model.cd_consumption[t]
        model.couple = pyomo.Constraint(self.city_district.model.t, rule=p_el_couple_rule)
        return

    def _add_objective(self):
        for node, entity in zip(self.nodes, self.entities):
            node.model.o = pyomo.Objective(expr=node.model.beta * entity.get_objective())
        return

    def _presolve(self, full_update, beta, robustness, debug):
        results, params = super()._presolve(full_update, beta, robustness, debug)
        for entity in self.entities:
            entity.model.beta = self._get_beta(params, beta)
        for node in self.nodes[1:]:
            if full_update:
                node.full_update(robustness=robustness)
            else:
                node.obj_update()
        return results, params

    def _solve(self, results, params, debug):
        self._solve_nodes(results, params, self.nodes[1:], variables=None, debug=debug)
        for entity in self.entities[1:]:
            entity.update_schedule()
        for t in range(len(self.nodes[0].model.cd_consumption)):
            self.nodes[0].model.cd_consumption[t] = sum(entity.p_el_schedule[t] for entity in self.entities[1:])
        self.nodes[0].full_update(params["robustness"])
        self.nodes[0].solve(variables=None, debug=debug)
        self._save_time(results, params)
        return

    def _postsolve(self, results, params, debug):
        self.entities[0].update_schedule()
        return
