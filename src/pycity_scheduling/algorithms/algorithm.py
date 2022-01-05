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
import time
import pyomo.environ as pyomo
from pyomo.solvers.plugins.solvers.persistent_solver import PersistentSolver
from pyomo.opt import SolverStatus, TerminationCondition

from pycity_scheduling.classes import CityDistrict, Building
from pycity_scheduling.exceptions import NonoptimalError, MaxIterationError
from pycity_scheduling.solvers import DEFAULT_SOLVER, DEFAULT_SOLVER_OPTIONS


class OptimizationAlgorithm:
    """
    Base class for all optimization algorithms.

    This class provides functionality common to all algorithms which are
    able to optimize City Districts.

    Parameters
    ----------
    city_district : CityDistrict
    solver : str, optional
        Solver to use for solving (sub-)problems.
    solver_options : dict, optional
        Options to pass to calls to the solver. Keys are the name of
        the functions being called and are one of `__call__`, `set_instance`,
        `solve`.

        - `__call__` is the function being called when generating an instance
          with the pyomo SolverFactory.  Additionally to the options provided,
          `node_ids` is passed to this call containing the IDs of the entities
          being optimized.
        - `set_instance` is called when a pyomo Model is set as an instance of
          a persistent solver.
        - `solve` is called to perform an optimization. If not set,
          `save_results` and `load_solutions` may be set to false to provide a
          speedup.

    mode : str, optional
        Specifies which set of constraints to use.

        - `convex`  : Use linear constraints
        - `integer`  : May use non-linear constraints
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    """

    def __init__(self, city_district, solver=DEFAULT_SOLVER, solver_options=DEFAULT_SOLVER_OPTIONS, mode="convex"):
        self.city_district = city_district
        self.entities = [city_district]
        self.entities.extend([node["entity"] for node in city_district.nodes.values()])
        self.solver = solver
        self.solver_options = solver_options
        self.mode = mode

    def _add_objective(self):
        """Adds the modified objective of the entities to their specific models."""
        raise NotImplementedError("This method should be implemented by subclass.")

    def solve(self, full_update=True, beta=1, robustness=None, debug=True):
        """Solves the city district for the current op_horizon.

        Parameters
        ----------
        full_update : bool, optional
            Should be true if the city district models were changed or
            update_model should be called to update the city district models.
            Disabling the full_update can give a small performance gain.
        beta : float, optional
            Tradeoff factor between system and customer objective. The customer
            objective is multiplied with beta.
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        debug : bool, optional
            Specify whether detailed debug information shall be printed.

        Returns
        -------
        results : dict
            Dictionary of performance values of the algorithm.

        Raises
        ------
        NonoptimalError
            If no feasible solution for the city district is found or a solver
            problem is encountered.
        """
        results, params = self._presolve(full_update, beta, robustness, debug)
        params["start_time"] = time.monotonic()
        self._solve(results, params, debug)
        self._postsolve(results, params, debug)
        return results

    def _save_time(self, results, params):
        """Saves the current runtime into results."""
        results["times"].append(time.monotonic() - params["start_time"])
        return

    @staticmethod
    def _get_beta(params, entity):
        """Returns the beta value for a specific entity."""
        beta = params["beta"]
        if isinstance(beta, dict):
            return beta.get(entity.id, 1.0)
        if isinstance(entity, CityDistrict):
            return 1.0
        return beta

    def _presolve(self, full_update, beta, robustness, debug):
        """Step before the optimization of (sub-)problems.

        Parameters
        ----------
        full_update : bool
            Should be true if the city district models were changed or
            update_model should be called to update the city district models.
            Disabling the full_update can give a small performance gain.
        beta : float
            Tradeoff factor between system and customer objective. The customer
            objective is multiplied with beta.
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        debug : bool, optional
            Specify whether detailed debug information shall be printed.

        Returns
        -------
        results : dict
            Dictionary in which performance values of the algorithm can be stored.
        params : dict
            Dictionary in which the algorithm can store intermediate results for
            later access in the algorithm itself. This dictionary should contain
            all which is generated and used by the algorithm.
        """
        params = {"beta": beta, "robustness": robustness}
        results = {"times": []}
        return results, params

    def _solve(self, results, params, debug):
        """Step in which (sub-)problems are optimized.

        Parameters
        ----------
        results : dict
            Dictionary in which performance values of the algorithm are stored.
        params : dict
            Dictionary in which intermediate results are stored.
        debug : bool
            Specify whether detailed debug information shall be printed.
        """
        raise NotImplementedError("This method should be implemented by subclass.")

    def _postsolve(self, results, params, debug):
        """Step after optimization.

        In this step the schedule can be updated and other post-processing can be done.

        Parameters
        ----------
        results : dict
            Dictionary in which performance values of the algorithm are stored.
        params : dict
            Dictionary in which intermediate results are stored.
        debug : bool
            Specify whether detailed debug information shall be printed.
        """
        for entity in self.entities:
            entity.update_schedule()
        return


class IterationAlgorithm(OptimizationAlgorithm):
    """Base class for all optimization algorithms that solve the problem iteratively."""
    def _solve(self, results, params, debug):
        if "iterations" not in results:
            results["iterations"] = []
        iterations = results["iterations"]
        is_last_iteration = False
        while not is_last_iteration:
            iterations.append((iterations[-1] + 1) if len(iterations) > 0 else 1)
            self._iteration(results, params, debug=debug)
            self._save_time(results, params)
            is_last_iteration = self._is_last_iteration(results, params)
        return

    def _iteration(self, results, params, debug):
        """Execute a single iteration of the algorithm.

        Parameters
        ----------
        results : dict
            Dictionary in which performance values of the algorithm are stored.
        params : dict
            Dictionary in which intermediate results are stored.
        debug : bool, optional
            Specify whether detailed debug information shall be printed.
        Raises
        ------
        MaxIterationError
            If the stopping criteria can not be reached in max_iterations.
        NonoptimalError
            If no feasible solution for the city district is found or a solver
            problem is encountered.
        """
        if results["iterations"][-1] > self.max_iterations:
            if debug:
                print(
                    "Exceeded iteration limit of {0} iterations. "
                    "Norms are ||r|| =  {1}, ||s|| = {2}."
                        .format(self.max_iterations, results["r_norms"][-1], results["s_norms"][-1])
                )
            raise MaxIterationError("Iteration Limit exceeded.")
        return

    def _is_last_iteration(self, results, params):
        """Returns True if the current iteration is the last one."""
        raise NotImplementedError("This method should be implemented by subclass.")


class DistributedAlgorithm(OptimizationAlgorithm):
    """Base class for all distributed optimization algorithms.

    These algorithms can divide the optimization problem into sub-problems.
    """
    def _solve_nodes(self, results, params, nodes, variables=None, debug=True):
        """Used to indicate which nodes can be solved independently.

        Provides the "distributed_times" as a performance value to results.

        Parameters
        ----------
        results : dict
            Dictionary in which performance values of the algorithm are stored.
        params : dict
            Dictionary in which intermediate results are stored.
        nodes : list of SolverNode
            List of nodes which can be solved independently.
        variables : list of list of variables, optional
            Can contain a list for each node in nodes to indicate to pyomo which
            variables should be loaded back into the model. Specifying this can
            lead to a significant speedup.
        debug : bool, optional
            Specify whether detailed debug information shall be printed. Defaults
            to true.
        """
        if "distributed_times" not in results:
            results["distributed_times"] = []
        if variables is None:
            variables = [None] * len(nodes)
        node_times = {}
        for node, variables_ in zip(nodes, variables):
            start = time.monotonic()
            node.solve(variables=variables_, debug=debug)
            stop = time.monotonic()

            entity_ids = tuple(entity.id for entity in node.entities)
            node_times[entity_ids] = stop - start
        results["distributed_times"].append(node_times)
        return

    def _postsolve(self, results, params, debug):
        for node in self.nodes:
            node.load_vars()
        super()._postsolve(results, params, debug)
        return


class SolverNode:
    """Node which can be used to solve all entities provided to it.

    Provides an abstraction layer for algorithms, so entities can be
    assigned to nodes and optimized easily.

    Parameters
    ----------
    solver : str
        Solver to use for solving (sub)problems.
    solver_options : dict, optional
        Options to pass to calls to the solver. Keys are the name of
        the functions being called and are one of `__call__`, `set_instance_`,
        `solve`.

        - `__call__` is the function being called when generating an instance
          with the pyomo SolverFactory.  Additionally to the options provided,
          `node_ids` is passed to this call containing the IDs of the entities
          being optimized.
        - `set_instance` is called when a pyomo Model is set as an instance of
          a persistent solver.
        - `solve` is called to perform an optimization. If not set,
          `save_results` and `load_solutions` may be set to false to provide a
          speedup.
    entities : list
        List of entities which should be optimized by this node.
    mode : str, optional
        Specifies which set of constraints to use.

        - `convex`  : Use linear constraints
        - `integer`  : May use non-linear constraints
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    """
    def __init__(self, solver, solver_options, entities, mode="convex", robustness=None):
        self.solver = pyomo.SolverFactory(solver, node_ids=[entity.id for entity in entities],
                                          **solver_options.get("__call__", {}))
        self.solver_options = solver_options
        self.is_persistent = isinstance(self.solver, PersistentSolver)
        self.robustness = robustness
        self.entities = entities
        self.mode = mode
        self.model = None
        self._prepare()

    def _prepare(self):
        """Create the pyomo model for the entities and populate it."""
        model = pyomo.ConcreteModel()
        for entity in self.entities:
            self._prepare_model(entity, model, robustness=self.robustness)
        self.model = model
        return

    def _prepare_model(self, entity, model, robustness=None):
        """Add a single entity to a model."""
        if isinstance(entity, Building):
            entity.populate_model(model, self.mode, robustness=robustness)
        else:
            entity.populate_model(model, self.mode)
        return

    def full_update(self, robustness=None):
        """Execute the update_model function and propagate other model changes.

        Parameters
        ----------
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        """
        for entity in self.entities:
            if isinstance(entity, Building):
                entity.update_model(mode=self.mode, robustness=robustness)
            else:
                entity.update_model(mode=self.mode)
        if self.is_persistent:
            self.solver.set_instance(self.model, **self.solver_options.get("set_instance", {}))
        return

    def obj_update(self):
        """Only propagate the objective value update of the model."""
        if self.is_persistent:
            self.solver.set_objective(self.model.o)
        else:
            pass
        return

    def solve(self, variables=None, debug=True):
        """Call the solver to solve this nodes optimization problem.

        Parameters
        ----------
        variables : list of list of variables, optional
            Can contain a list for each node in nodes to indicate to pyomo which
            variables should be loaded back into the model. Specifying this can
            lead to a significant speedup.
        debug : bool, optional
            Specify whether detailed debug information shall be printed. Defaults
            to true.
        """
        solve_options = self.solver_options.get("solve", {})
        if self.is_persistent:
            if variables is None:
                result = self.solver.solve(**solve_options)
            else:
                if "save_results" not in solve_options and "load_solutions" not in solve_options:
                    solve_options = solve_options.copy()
                    solve_options["save_results"] = False
                    solve_options["load_solutions"] = False
                result = self.solver.solve(**solve_options)
        else:
            result = self.solver.solve(self.model, **solve_options)
        if result.solver.termination_condition != TerminationCondition.optimal or \
                result.solver.status != SolverStatus.ok:
            if debug:
                import pycity_scheduling.util.debug as debug
                debug.analyze_model(self.model, self.solver, result)
            raise NonoptimalError("Could not retrieve schedule from model.")
        if self.is_persistent and variables is not None:
            self.solver.load_vars(variables)
        return

    def load_vars(self):
        """Load all remaining variables that were not loaded at the last 'solve' call."""
        if self.is_persistent:
            self.solver.load_vars()
        return
