import math

import numpy as np
import pyomo.environ as pyomo

from .write_csv import schedule_to_csv


__all__ = [
    'populate_models',
    'schedule_to_csv',
    'get_uncertainty',
    'compute_profile',
    'get_schedule',
]


def get_uncertainty(sigma, timesteps):
    """Compute uncertainty factors with constant standard deviation.

    Calculates the sigma and my for the normal distribution, which lead to a
    sigma as specified and a my of 1 for the corresponding lognormal
    distribution. These are then used to generate `timesteps` factors.

    Parameters
    ----------
    sigma : float
        Sigma of the lognormal distribution.
    timesteps : int
        Number of time steps for which uncertainty factors shall be generated.

    Notes
    -----
     - This function is supposed to be used once at the beginning of the
       simulation.
    """
    sigma_normal = math.sqrt(math.log(sigma**2+1))
    my_normal = -sigma_normal**2/2
    return np.random.lognormal(my_normal, sigma_normal, timesteps)


def get_incr_uncertainty(sigma, timesteps, first_timestep):
    """Compute uncertainty factors with increasing standard deviation.

    All time steps up to `first_timestep` get no uncertainty (factor of `1`).
    For the following time steps samples are drawn from a lognormal
    distribution with linearly increasing standard deviation. The standard
    deviation of the last time steps is `sigma`.

    Parameters
    ----------
    sigma : float
        Standard deviation of the last time step.
    timesteps : int
        Total number of time steps for which factors shall be generated.
    first_timestep : int
        First time step, from which on uncertainties are generated.

    Returns
    -------
    numpy.ndarray :
        Uncertainty factors.

    Notes
    -----
     - This function is supposed to be used before each optimization, where
       `first_timestep` is the time step indicating the current scheduling
       period.
    """
    length = timesteps - first_timestep
    incr_sigmas = np.arange(1, length + 1) * sigma / length
    sigmas_normal = np.sqrt(np.log(incr_sigmas**2+1))
    mys_normal = -sigmas_normal**2/2
    p2 = np.random.lognormal(mys_normal, sigmas_normal)
    p1 = np.ones(first_timestep)
    return np.concatenate((p1, p2))


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


def populate_models(city_district, mode, algorithm, robustness):
    """Create/Populate optimization models for scheduling.

    Creates Gurobi model(s) for scheduling. One model for reference, local and
    central scheduling and multiple models (one for each node and one for the
    aggregator) for different optimization algorithms.

    Parameters
    ----------
    city_district : pycity_scheduling.classes.CityDistrict
        District for which models shall be generated.
    mode : str
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : May use non-linear constraints
    algorithm : str
        Define which algorithm the models are used for. Must be one of
        'exchange-admm', 'dual-decompostition', 'stand-alone', 'local' or
        'central'.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    Returns
    -------
    dict :
        int -> pyomo.ConcreteModel
        `0` : Central or aggregator model.
        node ids : Bulding models.
    """
    op_horizon = city_district.op_horizon
    op_time_vec = city_district.op_time_vec
    nodes = city_district.node

    # create dictionary
    models = {}
    if algorithm in ['stand-alone', 'local', 'central']:
        m = pyomo.ConcreteModel()
        P_El_var_list = []
        for node in nodes.values():
            entity = node['entity']
            entity.populate_model(m, mode, robustness)
            P_El_var_list.append(entity.model.P_El_vars)
        city_district.populate_model(m, mode)
        def p_el_couple_rule(model, t):
            return city_district.model.P_El_vars[t] == pyomo.quicksum(P_El_var[t] for P_El_var in P_El_var_list)
        m.p_coupl_constr = pyomo.Constraint(city_district.model.t, rule=p_el_couple_rule)
        models[0] = m
    elif algorithm in ['exchange-admm', 'dual-decomposition']:
        m = pyomo.ConcreteModel()
        city_district.populate_model(m, mode)
        models[0] = m
        for node_id, node in nodes.items():
            m = pyomo.ConcreteModel()
            node['entity'].populate_model(m, mode, robustness)
            models[node_id] = m
    return models


def get_schedule(entity, schedule_type=None, timestep=None, energy=False,
                 thermal=False):
    """Retrieve a schedule from an OptimizationEntity.

    Parameters
    ----------
    entity : pycity_scheduling.classes.OptimizationEntity
        Entity to retrieve the schedule from.
    schedule_type : str, optional
        Specify which schedule to use.
        `None` : Current schedule
        'default' : Normal schedule
        'Ref', 'reference' : Reference schedule
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
    import warnings
    warnings.warn("get_schedule() is deprecated; use entity.schedules instead", DeprecationWarning)
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
    sched = entity.__getattr__(schedule_name)
    if timestep:
        sched = sched[:timestep]
    return sched
