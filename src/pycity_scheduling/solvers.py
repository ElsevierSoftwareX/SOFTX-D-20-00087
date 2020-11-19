"""
The pycity_scheduling Framework


Institution:
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


# Specify different third-party mathematical programming solvers and solver options:

SCIP_SOLVER = "scip"
SCIP_SOLVER_OPTIONS = {'solve': {'options': {}}}

BONMIN_SOLVER = "bonmin"
BONMIN_SOLVER_OPTIONS = {'solve': {'options': {'bonmin.algorithm': 'b-hyb',
                                               'bonmin.allowable_gap': 1e-10,
                                               'bonmin.allowable_fraction_gap': 1e-4}}}

GUROBI_DIRECT_SOLVER = "gurobi_direct"
GUROBI_DIRECT_SOLVER_OPTIONS = {'solve': {'options': {'OutputFlag': 0,
                                                      'LogToConsole': 0,
                                                      'Logfile': "",
                                                      "Method": 1}}}

GUROBI_PERSISTENT_SOLVER = "gurobi_persistent"
GUROBI_PERSISTENT_SOLVER_OPTIONS = {'solve': {'options': {'OutputFlag': 0,
                                                          'LogToConsole': 0,
                                                          'Logfile': "",
                                                          "Method": 1}}}

CPLEX_SOLVER = "cplex"
CPLEX_SOLVER_OPTIONS = {'solve': {'options': {}}}


# Set the default mathematical programming solver to be used by the pycity_scheduling framework:
DEFAULT_SOLVER = SCIP_SOLVER
DEFAULT_SOLVER_OPTIONS = SCIP_SOLVER_OPTIONS
