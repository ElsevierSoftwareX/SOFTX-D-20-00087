import numpy as np
from gurobipy import GRB

from .populate_models import populate_models
from .write_csv import schedule_to_csv


__all__ = [
    'populate_models',
    'schedule_to_csv',
    'get_normal_params',
    'compute_profile',
    'get_schedule',
]


def get_normal_params(sigma_lognormal):
    """Calculates the sigma and my for a normal distribution.

    Calculates the sigma and my for the normal distribution, which lead to a
    sigma as specified and a my of 1 for the corresponding lognormal
    distribution.

    Parameters
    ----------
    sigma_lognormal : float
        Sigma of the lognormal distribution.

    Returns
    -------
    float :
        Sigma of the normal distribution.
    float :
        My of the normal distribution.
    """
    import math
    sigma_normal = math.sqrt(math.log(sigma_lognormal**2+1))
    my_normal = -sigma_normal**2/2
    return sigma_normal, my_normal


def compute_profile(timer, profile, pattern=None):
    """

    Parameters
    ----------
    timer : pycity_scheduling.classes.Timer
    profile : array of binaries
        Indicator when electrical vehicle can be charged.
        `profile[t] == 0`: EV cannot be charged in t
        `profile[t] == 1`: EV can be charged in t
        It must contain at least one `0` otherwise the model will become
        infeasible. Its length has to be consistent with `pattern`.
    pattern : str, optional
        Define how the `profile` is to be used
        `None` : Profile matches simulation horizon.
        'daily' : Profile matches one day.
        'weekly' : Profile matches one week.

    Returns
    -------

    """
    if pattern is None:
        if len(profile) != timer.simu_horizon:
            raise ValueError(
                "Length of `profile` does not match `self.simu_horizon`. "
                "Expected: {}, Got: {}"
                .format(timer.simu_horizon, len(profile))
            )
        else:
            return profile
    elif pattern == 'daily':
        ts_per_day = int(86400 / timer.timeDiscretization)
        if len(profile) != ts_per_day:
            raise ValueError(
                "Length of `profile` does not match one day. Expected: {}, "
                "Got: {}".format(ts_per_day, len(profile))
            )
        else:
            days = int(timer.simu_horizon / ts_per_day) + 2
            ts = timer.time_in_day(from_init=True)
            return np.tile(profile, days)[ts:ts + timer.simu_horizon]
    elif pattern == 'weekly':
        ts_per_week = int(604800 / timer.timeDiscretization)
        if len(profile) != ts_per_week:
            raise ValueError(
                "Length of `profile` does not match one week. Expected: {}, "
                "Got: {}".format(ts_per_week, len(profile))
            )
        else:
            weeks = int(timer.simu_horizon / ts_per_week) + 2
            ts = timer.time_in_week(from_init=True)
            return np.tile(profile, weeks)[ts:ts + timer.simu_horizon]
    else:
        raise ValueError(
            "Unknown `pattern`: {}. Must be `None`, 'daily' or 'weekly'."
            .format(pattern)
        )


def get_schedule(entity, reference=False, timestep=None,
                 energy=False, thermal=False):
    """Retrieve a schedule from an OptimizationEntity.

    Parameters
    ----------
    entity : pycity_scheduling.classes.OptimizationEntity
        Entity to retrieve the schedule from.
    reference : bool, optional
        If `True` retrieve reference schedule.
        If `False` retrieve normal schedule.
    timestep : int, optional
        If specified, trim schedule to this timestep.
    energy : bool, optional
        If `True` retrieve energy schedule.
        If `False` retrieve power schedule.
    thermal : bool, optional
        If `True` retrieve thermal schedule.
        If `False` retrieve electric schedule.

    Returns
    -------
    np.ndarray :
        Specified schedule.

    Raises
    ------
    KeyError :
        When specified schedule cannot be found.
    """
    schedule_name = 'E_' if energy else 'P_'
    schedule_name += 'Th_' if thermal else 'El_'
    schedule_name += 'Ref_' if reference else ''
    schedule_name += 'Schedule'
    sched = entity.__dict__.get(schedule_name)
    if timestep:
        sched = sched[:timestep]
    return sched


_status_codes = [
    'LOADED',
    'OPTIMAL',
    'INFEASIBLE',
    'INF_OR_UNBD',
    'UNBOUNDED',
    'CUTOFF',
    'ITERATION_LIMIT',
    'NODE_LIMIT',
    'TIME_LIMIT',
    'SOLUTION_LIMIT',
    'INTERRUPTED',
    'NUMERIC',
    'SUBOPTIMAL',
    'INPROGRESS',
    'USER_OBJ_LIMIT',
]

status_codes_map = {eval(c, {}, GRB.__dict__): c for c in _status_codes}


def analyze_model(model, exception=None):
    """Analyze a Gurobi model which is not optimal.

    Parameters
    ----------
    model : gurobipy.Model
        Model with `status != GRB.OPTIAML`
    exception : Exception, optional
        Original exception, whose message will be printed
    """
    model.setParam('OutputFlag', True)
    if model.status == GRB.INF_OR_UNBD:
        model.dualreductions = 0
        model.optimize()
    status = model.status
    print("Model status is {}.".format(status_codes_map[status]))
    if exception:
        print("Original Error:")
        print(exception)
    if status == GRB.INFEASIBLE:
        model.computeIIS()
        model.write('model.ilp')
        print("IIS written to 'model.ilp'.")
