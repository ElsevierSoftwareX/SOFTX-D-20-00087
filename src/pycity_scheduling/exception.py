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


class SchedulingError(Exception):
    """
    Exception raised, when a scheduling fails.
    """


class MaxIterationError(SchedulingError):
    """
    Exception raised, when the maximum number of iterations (by a distributed algorithm) is reached.
    """


class NonoptimalError(SchedulingError):
    """
    Exception raised, when a model did not converge towards an optimal solution.
    """
