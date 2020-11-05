"""
:::::::::::::::::::::::::::::::::::::::
::: The pycity_scheduling Framework :::
:::::::::::::::::::::::::::::::::::::::


Institution:
::::::::::::
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
::::::::
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.algorithms.algorithm import OptimizationAlgorithm, SolverNode
from pycity_scheduling.constants import DEFAULT_SOLVER, DEFAULT_SOLVER_OPTIONS


class CentralOptimization(OptimizationAlgorithm):
    """ Implementation of a central Algorithm.

        Only creates one model and calls the solver only once. Combines the
        objectives of all entities.
    """
    def __init__(self, city_district, solver=DEFAULT_SOLVER, solver_options=DEFAULT_SOLVER_OPTIONS, mode="convex",
                 robustness=None):
        super(CentralOptimization, self).__init__(city_district, solver, solver_options, mode)
        # create single solver node for all entities
        self.node = SolverNode(solver, solver_options, self.entities, mode, robustness=robustness)
        # add coupling between all entities in the single model
        self._add_coupling(self.node.model)
        # create pyomo parameters for beta of each entity
        for entity in self.entities:
            entity.model.beta = pyomo.Param(mutable=True, initialize=1)
        self._add_objective()

    def _add_coupling(self, model):
        """Adds the coupling constraint to the model.

        This constraint 'connects' the district operator to all its nodes.

        Parameters
        ----------
        model : pyomo.ConcreteModel
            Model to add the constraint to.
        """
        def p_el_couple_rule(model, t):
            return self.city_district.model.p_el_vars[t] == \
                   pyomo.quicksum(entity.model.p_el_vars[t] for entity in self.entities[1:])
        model.couple = pyomo.Constraint(self.city_district.model.t, rule=p_el_couple_rule)
        return

    def _add_objective(self):
        self.node.model.o = pyomo.Objective(expr=pyomo.quicksum(entity.model.beta * entity.get_objective()
                                                                for entity in self.entities))
        return

    def _presolve(self, full_update, beta, robustness, debug):
        results, params = super()._presolve(full_update, beta, robustness, debug)
        for entity in self.entities:
            entity.model.beta = self._get_beta(params, beta)
        if full_update:
            self.node.full_update(robustness=robustness)
        else:
            self.node.obj_update()
        return results, params

    def _solve(self, results, params, debug):
        self.node.solve(variables=None, debug=debug)
        self._save_time(results, params)
        return
