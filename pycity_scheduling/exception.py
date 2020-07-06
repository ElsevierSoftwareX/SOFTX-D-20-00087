class SchedulingError(Exception):
    """Exception raised, when a scheduling fails."""


class MaxIterationError(SchedulingError):
    """Exception raised, when the maximum number of iterations is reached."""


class NonoptimalError(SchedulingError):
    """Exception raised, when a model does not lead to an optimal solution."""
