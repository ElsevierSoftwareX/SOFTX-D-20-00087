class PyCitySchedulingException(Exception):
    """Base class for all exceptions in pycity_scheduling"""


class PyCitySchedulingMaxIteration(PyCitySchedulingException):
    """Exception raised, when number of maximum iterations is reached"""


class PyCitySchedulingGurobiException(PyCitySchedulingException):
    """Exception raised, when GurobiExceptions are encountered"""


class PyCitySchedulingInitError(PyCitySchedulingException):
    """Exception raised, when Init of a class fails due to inconsitent data"""
