import math

import numpy as np

from .populate_models import populate_models
from .write_csv import schedule_to_csv


__all__ = [
    'populate_models',
    'schedule_to_csv',
    'get_uncertainty',
    'compute_profile',
    'get_schedule',
]


def get_uncertainty(sigma, timesteps):
    """Calculate uncertainty factors for each timestep.

    Calculates the sigma and my for the normal distribution, which lead to a
    sigma as specified and a my of 1 for the corresponding lognormal
    distribution. These are then used to generate `timesteps` factors.

    Parameters
    ----------
    sigma : float
        Sigma of the lognormal distribution.
    timesteps : int
        Number of time steps for which uncertainty factors shall be generated.
    """
    sigma_normal = math.sqrt(math.log(sigma**2+1))
    my_normal = -sigma_normal**2/2
    return np.random.lognormal(my_normal, sigma_normal, timesteps)


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


def get_schedule(entity, schedule_type=None, timestep=None, energy=False,
                 thermal=False):
    """Retrieve a schedule from an OptimizationEntity.

    Parameters
    ----------
    entity : pycity_scheduling.classes.OptimizationEntity
        Entity to retrieve the schedule from.
    schedule_type : str, optional
        Specify which schedule to use.
        `None` : Normal schedule
        'act', 'actual' : Actual schedule
        'ref', 'reference' : Reference schedule
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
    numpy.ndarray :
        Specified schedule.

    Raises
    ------
    ValueError:
        When an unknown `schedule_type` is given.
    KeyError :
        When specified schedule cannot be found.
    """
    schedule_name = 'E_' if energy else 'P_'
    schedule_name += 'Th_' if thermal else 'El_'
    if schedule_type is None:
        pass
    elif schedule_type.lower() in ['act', 'actual']:
        schedule_name += 'Act_'
    elif schedule_type.lower() in ['ref', 'reference']:
        schedule_name += 'Ref_'
    else:
        raise ValueError(
            "Unknown `schedule_type`: '{}'. Must be `None`, 'act' or 'ref'."
            .format(schedule_type)
        )
    schedule_name += 'Schedule'
    sched = entity.__dict__.get(schedule_name)
    if timestep:
        sched = sched[:timestep]
    return sched
