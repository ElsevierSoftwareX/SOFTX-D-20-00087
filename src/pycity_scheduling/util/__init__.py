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
import pyomo.environ as pyomo

from pycity_scheduling.util.write_schedules import schedule_to_csv, schedule_to_json
from pycity_scheduling.exceptions import SchedulingError


__all__ = [
    'compute_profile',
    'calculate_flexibility_potential',
    'extract_pyomo_value',
    'extract_pyomo_values',
]


def compute_profile(timer, profile, pattern=None):
    """
    Compute a load series profile for an electrical vehicle.

    Parameters
    ----------
    timer : pycity_scheduling.classes.Timer
    profile : array of binaries
        Indicator when electrical vehicle can be charged.

        - `profile[t] == 0`: EV cannot be charged in t
        - `profile[t] == 1`: EV can be charged in t
        It must contain at least one `0` otherwise the model will become
        infeasible. Its length has to be consistent with `pattern`.
    pattern : str, optional
        Define how the `profile` is to be used.

        - `None` : Profile matches simulation horizon.
        - 'daily' : Profile matches one day.
        - 'weekly' : Profile matches one week.

    Returns
    -------
        numpy.ndarray
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
        ts_per_day = int(86400 / timer.time_discretization)
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
        ts_per_week = int(604800 / timer.time_discretization)
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


def calculate_flexibility_potential(city_district, algorithm="central", reference_algorithm="stand-alone"):
    """
    Calculate and quantify the operational flexibility potential for a certain city district.


    Parameters
    ----------
    city_district : pycity_scheduling.classes.CityDistrict
        District for which the flexibility potential should be quantified.
    algorithm : str
        Define which algorithm should be used for the flexibility potential quantification purposes.
        Must be one of 'exchange-admm', 'dual-decomposition', 'stand-alone', 'local' or 'central'.
        Default: 'central'.
    reference_algorithm : str
        Define which algorithm should be used as the reference for the flexibility potential quantification purposes.
        Must be one of 'exchange-admm', 'dual-decomposition', 'stand-alone', 'local' or 'central'.
        Default: 'stand-alone'.

    Returns
    -------
    float :
        City district operational flexibility potential in kWh.
    """
    from pycity_scheduling.util.metric import absolute_flexibility_gain
    from pycity_scheduling.algorithms import algorithms

    city_district.copy_schedule(dst="tmp")

    f = algorithms[reference_algorithm](city_district)
    f.solve()
    city_district.copy_schedule("flexibility-potential-quantification-ref")
    f = algorithms[algorithm](city_district)
    f.solve()
    flex = absolute_flexibility_gain(city_district, "flexibility-potential-quantification-ref")

    city_district.copy_schedule(src="tmp")
    return flex


def _known_domains(variable):
    if not variable.is_integer():
        return float
    elif variable.is_binary():
        return bool
    else:
        return int


_numpy_type = {
    float: np.float64,
    int: np.int,
    bool: np.bool
}


def extract_pyomo_value(variable, var_type=None):
    """
    Extract a single values out of the pyomo Variable after optimization.

    Parameters
    ----------
    variable : pyomo.Var
        Variable to extract value from.

    var_type : type, optional
        Type with which variable should be stored. Defaults to Domain of pyomo Variable Container or float.

        - float : Store values as floating point numbers.
        - int : Store values as integers (rounding down if necessary).
        - bool : Store values as binary values.

    Returns
    -------
    float or int or bool:
        Extracted value from the pyomo Variable or the closest value to zero if stale.

    Raises
    ------
    SchedulingError
        If value to extract is not feasible.
    """
    if var_type is None:
        var_type = _known_domains(variable)

    if not hasattr(variable, "stale"):
        raise ValueError("Variable Container does not appear to have been scheduled.")

    if variable.is_indexed():
        raise ValueError("For indexed variables 'extract_pyomo_values' should be used.")

    if variable.stale is True:
        # if stale select closest feasible value to zero
        value = 0
        if variable.ub is not None and variable.ub < 0:
            value = variable.ub
        elif variable.lb is not None and variable.lb > 0:
            value = variable.lb

        if var_type is int:
            if value > 0:
                value = np.ceil(value)
            elif value < 0:
                value = np.floor(value)
        elif var_type is bool:
            if value != 0:
                value = 1

        if (variable.lb is not None and variable.lb > value) or \
           (variable.ub is not None and variable.ub < value):
            raise SchedulingError("Domain and/or bounds of variable render it infeasible.")
        return var_type(value)
    else:
        value = variable.value
    value = var_type(value)
    return value


def extract_pyomo_values(variable, var_type=None):
    """
    Extract values out of the pyomo Variable container after optimization.

    Parameters
    ----------
    variable : pyomo.Var
        Variable container to extract values from.

    var_type : type, optional
        Type with which variable should be stored. Defaults to Domain of pyomo Variable Container or float.

        - float : Store values as floating point numbers.
        - int : Store values as integers (rounding down if necessary).
        - bool : Store values as binary values.

    Returns
    -------
    numpy.ndarray or float or int or bool:
        If the Variable container is indexed an array containing the extracted values is returned.
        If the Variable container is not indexed returns the single extracted value.

    Raises
    ------
    SchedulingError
        If values to extract are not feasible.
    """

    if not variable.is_constructed():
        raise ValueError("Variable is not constructed.")

    if variable.is_indexed():
        if var_type is None:
            ts = list(_known_domains(v) for v in variable.values())
            if not all(t is ts[0] for t in ts):
                t = float
            else:
                t = ts[0]
        else:
            t = var_type
        dtype = _numpy_type[t]
        values = np.zeros(len(variable), dtype=dtype)
        for i, v in enumerate(variable.values()):
            values[i] = extract_pyomo_value(v, var_type=t)
        return values
    else:
        return extract_pyomo_value(variable, var_type)
