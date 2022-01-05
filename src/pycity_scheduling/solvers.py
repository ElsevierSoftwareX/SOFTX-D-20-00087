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


# Specify different third-party mathematical programming solvers and solver options:

BONMIN_SOLVER = "bonmin"
BONMIN_SOLVER_OPTIONS = {'solve': {'options': {'bonmin.algorithm': 'b-hyb',
                                               'bonmin.allowable_gap': 1e-10,
                                               'bonmin.allowable_fraction_gap': 1e-4}}}

CPLEX_SOLVER = "cplex"
CPLEX_SOLVER_OPTIONS = {'solve': {'options': {}}}

GLPK_SOLVER = "glpk"
GLPK_SOLVER_OPTIONS = {'solve': {'options': {}}}

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

SCIP_SOLVER = "scip"
SCIP_SOLVER_OPTIONS = {'solve': {'options': {}}}


# Set the default mathematical programming solver to be used by the pycity_scheduling framework:
DEFAULT_SOLVER = GUROBI_DIRECT_SOLVER
DEFAULT_SOLVER_OPTIONS = GUROBI_DIRECT_SOLVER_OPTIONS
