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

from pycity_scheduling import constants, classes
from pycity_scheduling.classes import Boiler, ElectricalEntity, CityDistrict


def calculate_costs(entity, timestep=None, prices=None, feedin_factor=None):
    """
    Calculate electricity costs for the entity with the current schedule.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate costs for.
    timestep : int, optional
        If specified, calculate metric only to this timestep.
    prices : array_like, optional
        Energy prices for simulation horizon.
    feedin_factor : float, optional
        Factor which is multiplied to the prices for feed-in revenue.

    Returns
    -------
    float :
        Electricity costs in [ct].
    """
    p = entity.p_el_schedule
    if prices is None:
        if isinstance(entity, CityDistrict):
            prices = entity.environment.prices.da_prices
        else:
            prices = entity.environment.prices.tou_prices
    if timestep:
        prices = prices[:timestep]
        p = p[:timestep]
    if feedin_factor is None:
        if isinstance(entity, CityDistrict):
            feedin_factor = 1
        else:
            feedin_factor = entity.environment.prices.feedin_factor
    costs = entity.time_slot * np.dot(prices[p > 0], p[p > 0])
    costs += entity.time_slot * np.dot(prices[p < 0], p[p < 0]) * feedin_factor
    return costs


def calculate_adj_costs(entity, schedule, timestep=None, prices=None, total_adjustments=True):
    """
    Calculate costs for power schedule adjustments.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate adjustment costs for.
    schedule : str, optional
       Schedule to adjust to.

       - 'default' : Default schedule
       - 'ref' : Reference schedule
    timestep : int, optional
        If specified, calculate metric only to this timestep.
    prices : array_like, optional
        Adjustment prices for all timesteps in simulation horizon.
    total_adjustments : bool, optional
        `True` if positive and negative deviations shall be considered.
        `False` if only positive deviations shall be considered.

    Returns
    -------
    float :
        Adjustment costs in [ct].
    """
    if prices is None:
        if isinstance(entity, CityDistrict):
            prices = entity.environment.prices.da_prices
        else:
            prices = entity.environment.prices.tou_prices
    if timestep:
        prices = prices[:timestep]
    adj_power = calculate_adj_power(entity, schedule, timestep, total_adjustments)
    costs = entity.time_slot * np.dot(adj_power, prices)
    return costs


def calculate_co2(entity, timestep=None, co2_emissions=None):
    """
    Calculate CO2 emissions for the entity with the current schedule.

    Parameters
    ----------
    entity : OptimizationEntity
        The entity to calculate co2 emission for.
    timestep : int, optional
        If specified, calculate metric only to this timestep.
    co2_emissions : array_like, optional
        Specific CO2 emissions for all timesteps in the simulation horizon in [g/kWh].

    Returns
    -------
    float :
        CO2 emissions in [g].
    """
    if isinstance(entity, Boiler):
        p = entity.p_th_heat_schedule
        if timestep is not None:
            p = p[:timestep]
        co2 = -(sum(p) * entity.time_slot / entity.eta
                * constants.CO2_EMISSIONS_GAS)
        return co2
    elif isinstance(entity, ElectricalEntity):
        if timestep is None:
            timestep = len(entity.p_el_schedule)
        p = entity.p_el_schedule[:timestep]
        if co2_emissions is None:
            co2_emissions = entity.environment.prices.co2_prices
        co2_emissions = co2_emissions[:timestep]
        bat_schedule = sum(
            e.p_el_schedule[:timestep]
            for e in classes.filter_entities(entity, 'BAT')
        )
        # ToDo: This approach neglects battery losses.
        p = p - bat_schedule
        co2 = entity.time_slot * np.dot(p[p>0], co2_emissions[p>0])
        gas_schedule = sum(
            e.p_th_heat_schedule[:timestep].sum()
            * (1+e.sigma) / e.omega
            for e in classes.filter_entities(entity, 'CHP')
        )
        gas_schedule += sum(
            e.p_th_heat_schedule[:timestep].sum()
            / e.eta
            for e in classes.filter_entities(entity, 'BL')
        )
        pv_schedule = sum(
            e.p_el_schedule[:timestep].sum()
            for e in classes.filter_entities(entity, 'PV')
        )
        wec_schedule = sum(
            e.p_el_schedule[:timestep].sum()
            for e in classes.filter_entities(entity, 'WEC')
        )
        co2 -= gas_schedule * entity.time_slot * constants.CO2_EMISSIONS_GAS
        co2 -= pv_schedule * entity.time_slot * constants.CO2_EMISSIONS_PV
        co2 -= wec_schedule * entity.time_slot * constants.CO2_EMISSIONS_WIND
        return co2
    else:
        raise NotImplementedError


def calculate_adj_power(entity, schedule, timestep=None, total_adjustments=True):
    """
    Compute the power schedule adjustments.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the power adjustment for.
    schedule : str, optional
       Schedule to adjust to.

       - 'default' : Default schedule
       - 'ref' : Reference schedule
    timestep : int, optional
        If specified, calculate metric only to this timestep.
    total_adjustments : bool, optional
        `True` if positive and negative deviations shall be considered.
        `False` if only positive deviations shall be considered.

    Returns
    -------
    array of float :
        Adjustment power in [kW].
    """
    adjustments = entity.schedules[schedule]["p_el"] - entity.p_el_schedule
    if timestep:
        adjustments = adjustments[:timestep]
    if total_adjustments:
        return abs(adjustments)
    else:
        return np.maximum(adjustments, 0)


def calculate_adj_energy(entity, schedule, timestep=None, total_adjustments=True):
    """
    Compute the cumulative absolute energy of all adjustments.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the energy adjustment for.
    schedule : str, optional
       Schedule to adjust to.

       - 'default' : Default schedule
       - 'ref' : Reference schedule
    timestep : int, optional
        If specified, calculate metric only to this timestep.
    total_adjustments : bool, optional
        `True` if positive and negative deviations shall be considered.
        `False` if only positive deviations shall be considered.

    Returns
    -------
    float :
        Adjustments in [kWh].
    """
    p = calculate_adj_power(entity, schedule, timestep, total_adjustments)
    adjustments = entity.time_slot * sum(p)
    return adjustments


def metric_delta_g(entity, schedule):
    """
    Compute the factor ∆g for the current schedule and the reference schedule.

    Parameters
    ----------
    entity : ElectricalEntity
        The Entity to calculate the delta g metric for.
    schedule : str
       Referenced Schedule

       - 'default' : Normal schedule
       - 'ref' : Reference schedule

    Returns
    -------
    float :
        Factor ∆g.

    Notes
    -----
    - Implementation as given in the lecture "Elektrizitaetswirtschaft"
      by Prof. Dr.-Ing. Christian Rehtanz from TU Dortmund, Germany.
    """
    p_el_min_dsm = min(entity.p_el_schedule)
    p_el_max_dsm = max(entity.p_el_schedule)
    p_el_min_ref = min(entity.schedules[schedule]["p_el"])
    p_el_max_ref = max(entity.schedules[schedule]["p_el"])
    g = 1.0 - (abs(p_el_max_dsm - p_el_min_dsm) / abs(p_el_max_ref - p_el_min_ref))
    return g


def peak_to_average_ratio(entity, timestep=None):
    """
    Compute the ratio of peak demand to the average demand.

    The ratio of the absolute peak demand of the specified schedule is
    compared to the absolute mean of the schedule.
    It holds `r` >= 1, where a lower value is `better`, 1.0 would be optimal (i.e. no peaks at all).

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the peak to avereage ratio for.
    timestep : int, optional
        If specified, calculate metric only to this timestep.

    Returns
    -------
    float :
        Peak to average ratio.
    """
    p = entity.p_el_schedule
    if timestep is not None:
        p = p[:timestep]
    peak = max(max(p), -min(p))
    mean = abs(np.mean(p))
    r = peak / mean
    return r


def peak_reduction_ratio(entity, schedule, timestep=None):
    """
    Compute the ratio of the peak reduction.

    The reduction of the absolute peak demand of the current schedule is
    compared to the peak demand in the reference schedule.
    If `r` < 1, the specified schedule has smaller peaks, otherwise the
    reference schedule has smaller peaks.
    Usually a small `r` value is the desired outcome.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the peak reduction ratio for.
    schedule : str
        Name of Schedule to compare to.

        - 'default' : Default schedule
        - 'ref' : Reference schedule
    timestep : int, optional
        If specified, calculate metric only to this timestep.

    Returns
    -------
    float :
        Peak reduction ratio.
    """
    if timestep is None:
        timestep = len(entity.p_el_schedule)
    p = entity.p_el_schedule[:timestep]
    ref = entity.schedules[schedule]["p_el"][:timestep]
    dr_peak = max(max(p), -min(p))
    ref_peak = max(max(ref), -min(ref))
    r = (dr_peak - ref_peak) / ref_peak
    return r


def self_consumption(entity, timestep=None):
    """
    Calculate the self-consumption rate for the current schedule.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the self-consumption rate for.
    timestep : int, optional
        If specified, calculate metric only to this timestep.

    Returns
    -------
    float :
        Self-consumption rate.
    """
    if timestep is None:
        timestep = len(entity.p_el_schedule)
    p = entity.p_el_schedule[:timestep]
    res_schedule = sum(e.p_el_schedule[:timestep] for e in classes.filter_entities(entity, 'generation_devices'))
    if not isinstance(res_schedule, np.ndarray):
        return 0
    generation = sum(res_schedule)
    if generation == 0:
        return 1
    neg_load = res_schedule - p
    np.clip(neg_load, a_min=None, a_max=0, out=neg_load)
    consumption = sum(np.maximum(neg_load, res_schedule))
    entity_consumption = consumption / generation
    return entity_consumption


def autarky(entity, timestep=None):
    """
    Calculate the autarky rate for the current schedule.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the autarky rate for.
    timestep : int, optional
        If specified, calculate metric only to this timestep.

    Returns
    -------
    float :
        Autarky rate.
    """
    if timestep is None:
        timestep = len(entity.p_el_schedule)
    p = entity.p_el_schedule[:timestep]
    res_schedule = - sum(e.p_el_schedule[:timestep] for e in classes.filter_entities(entity, 'generation_devices'))
    if not isinstance(res_schedule, np.ndarray):
        return 0
    load = p + res_schedule
    np.clip(load, a_min=0, a_max=None, out=load)
    consumption = sum(load)
    if consumption == 0:
        return 1
    cover = sum(np.minimum(res_schedule, load))
    autarky_val = cover / consumption
    return autarky_val


def absolute_flexibility_gain(entity, schedule, timestep=None):
    """
    Calculates the absolute flexibility gain for the entity with the current schedule.
    This corresponds to the amount of electrical energy shifted due to the selected objective function.

    Parameters
    ----------
    entity : ElectricalEntity
        The entity to calculate the absolute flexibility gain for.
    schedule : str
        Name of Schedule to compare to.

       - 'default' : Default schedule
       - 'ref' : Reference schedule
    timestep : int, optional
        If specified, calculate metric only to this timestep.

    Returns
    -------
    float :
        Absolute flexibility gain in [kWh].
    """
    if timestep is None:
        timestep = len(entity.p_el_schedule)
    p = entity.p_el_schedule[:timestep]
    ref = entity.schedules[schedule]["p_el"][:timestep]
    diff = ref - p
    np.clip(diff, a_min=0, a_max=None, out=diff)
    abs_flex = sum(diff) * entity.time_slot
    return abs_flex
