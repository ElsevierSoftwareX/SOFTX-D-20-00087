import random

import numpy as np
from shapely.geometry import Point

from pycity_scheduling.classes import *
from pycity_scheduling.data.tabula_data import tabula_building_data as tbd
from pycity_scheduling.data.ev_data import ev_data as evd


def generate_standard_environment(**timer_args):
    timer = Timer(**timer_args)
    weather = Weather(timer)
    prices = Prices(timer)
    environment = Environment(timer, weather, prices)
    return environment


def _calculate_ev_times(timer):
    length = int(3600/timer.timeDiscretization)
    ev_time_ranges = [
        [0] * (8 * length) + [1] * (12 * length) + [0] * (4 * length),
        [1] * (12 * length) + [0] * (12 * length),
        [0] * (12 * length) + [1] * (12 * length),
        [1] * (10 * length) + [0] * (12 * length) + [1] * (2 * length),
        [1] * (9 * length) + [0] * (12 * length) + [1] * (3 * length),
        [1] * (8 * length) + [0] * (12 * length) + [1] * (4 * length),
        [1] * (7 * length) + [0] * (12 * length) + [1] * (5 * length),
        [1] * (6 * length) + [0] * (12 * length) + [1] * (6 * length),
        [1] * (5 * length) + [0] * (12 * length) + [1] * (7 * length),
    ]
    return ev_time_ranges


def _calculate_dl_times(timer):
    length = int(3600/timer.timeDiscretization)
    dl_time_ranges = [
        [1] * (8 * length) + [0] * (16 * length),
        [0] * (8 * length) + [1] * (4 * length) + [0] * (12 * length),
        [0] * (12 * length) + [1] * (4 * length) + [0] * (8 * length),
        [0] * (16 * length) + [1] * (4 * length) + [0] * (4 * length),
        [0] * (20 * length) + [1] * (4 * length),
        [0] * (17 * length) + [1] * (4 * length) + [0] * (3 * length),
        [0] * (7 * length) + [1] * (4 * length) + [0] * (13 * length),
        [0] * (10 * length) + [1] * (4 * length) + [0] * (10 * length),
        [0] * (2 * length) + [1] * (4 * length) + [0] * (18 * length),
    ]
    return dl_time_ranges


def generate_tabula_buildings(environment,
                              number,
                              building_distribution=None,
                              heating_distribution=None,
                              device_probabilities=None,
                              objective='price',
                              seed=None):
    """Generate buildings based on the TABULA data.

    Generate buildings based on the TABULA data from: http://www.episcope.eu/
    Heating units are automatically dimensioned and added to each building. A
    TES always covers the thermal energy demand of a building for at least two
    hours.

    Parameters
    ----------
    environment : pycity_scheduling.classes.Environment
    number : int
        Number of houses to be generated.
    building_distribution : dict, optional
        The distribution of the houses among the tabula standard buildings. If
        omitted an equal distribution will be used.
        Keys : str
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys : str
            {'HP', 'EH', 'CHP', 'BL'}
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys : str
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values : sloat
            Number between 0 and 1.
    objective : str, optional
        The objective for all buildings.
    seed: int, optional
        Specify a seed for the randomization. If omitted, a non-deterministic
        city district will be generated.

    Returns
    ----------
    list of pycity_scheduling.classes.Building :
        List of generated buildings.
    """
    if building_distribution is None:
        share = 1/len(tbd)
        building_distribution = {b: share for b in tbd}
    if heating_distribution is None:
        share = 1/len(heating_devices)
        heating_distribution = {d: share for d in heating_devices}
    if device_probabilities is None:
        device_probabilities = {'FL': 1}

    building_dicts = []
    for building, share in building_distribution.items():
        building_dicts += [tbd[building]] * round(share * number)
    if len(building_dicts) != number:
        raise ValueError("Bad building distribution.")

    heating_list = []
    for heating, share in heating_distribution.items():
        heating_list += [heating_devices[heating]] * round(share * number)
    if len(heating_list) != number:
        raise ValueError("Bad heating distribution.")

    if any(map(lambda x: not 0 <= x <= 1, device_probabilities.values())):
        raise ValueError("Bad device probabilities")

    number_ap = sum(building['apartments'] for building in building_dicts)
    a = round(device_probabilities.get('FL', 0) * number_ap)
    fl_list = [True] * a + [False] * (number_ap - a)
    a = round(device_probabilities.get('DL', 0) * number_ap)
    dl_list = [True] * a + [False] * (number_ap - a)
    a = round(device_probabilities.get('EV', 0) * number_ap)
    ev_list = [True] * a + [False] * (number_ap - a)
    a = round(device_probabilities.get('PV', 0) * number)
    pv_list = [True] * a + [False] * (number_ap - a)
    a = round(device_probabilities.get('BAT', 0) * number)
    bat_list = [True] * a + [False] * (number_ap - a)

    ev_time_ranges = _calculate_ev_times(environment.timer)
    dl_time_ranges = _calculate_dl_times(environment.timer)

    if seed is not None:
        random.seed(seed)
    random.shuffle(heating_list)
    random.shuffle(fl_list)
    random.shuffle(dl_list)
    random.shuffle(pv_list)
    random.shuffle(ev_list)
    random.shuffle(bat_list)

    buildings = []
    ap_counter = 0

    # Generate buildings:
    for i, b in enumerate(building_dicts):
        building_type = b['building_type']
        name = 'BD{:03}_{}'.format(i + 1, building_type)

        bd = Building(environment, objective=objective, name=name,
                      profile_type=b['th_profile_type'],
                      building_type=building_type)

        bes = BuildingEnergySystem(environment)
        bd.addEntity(bes)

        ap_area = b['net_floor_area']/b['apartments']

        for n in range(b['apartments']):
            ap = Apartment(environment, ap_area)
            sh = SpaceHeating(environment, method=1, livingArea=ap_area,
                              specificDemand=b['th_demand'],
                              profile_type=b['th_profile_type'])
            ap.addEntity(sh)

            if fl_list[ap_counter]:
                fl = FixedLoad(environment, method=1,
                               annualDemand=b['el_demand'],
                               profileType=b['el_profile_type'])
                ap.addEntity(fl)

            if dl_list[ap_counter]:
                e_el = random.uniform(0.8, 4.5)
                p_el = random.uniform(1.125, 2.5)
                time = random.choice(dl_time_ranges)
                dl = DeferrableLoad(environment, P_El_Nom=p_el,
                                    E_Min_Consumption=e_el, load_time=time,
                                    lt_pattern='daily')
                ap.addEntity(dl)

            if ev_list[ap_counter]:
                ev_data = random.choice(list(evd.values()))
                ev_charging_time = random.choice(ev_time_ranges)
                soc = 0.5 if ev_data['charging_method'] == 'fast' else 0.75
                ev = ElectricalVehicle(environment,
                                       E_El_Max=ev_data['e_el_storage_max'],
                                       P_El_Max_Charge=ev_data['p_el_nom'],
                                       SOC_Ini=soc,
                                       charging_time=ev_charging_time,
                                       ct_pattern='daily')
                ap.addEntity(ev)

            bd.addEntity(ap)
            ap_counter += 1

        # TODO: Workaround for unstable implementation in pycity_base
        power_curve = bd.get_space_heating_power_curve()
        if len(power_curve) == 0:
            power_curve = [0]
        p_th_max = max(power_curve)/1000.0 + 1.0
        heating_device = heating_list[i](environment, P_Th_Nom=p_th_max)
        tes = ThermalEnergyStorage(environment, E_Th_Max=2.0*p_th_max,
                                   SOC_Ini=0.5, SOC_End=0.5, tMax=60.0,
                                   tSurroundings=20.0)
        bes.addDevice(heating_device)
        bes.addDevice(tes)

        if pv_list[i]:
            if b['roof_angle'] == 0.0:
                angle = 35.0
            else:
                angle = b['roof_angle']
            area = b['roof_area']/2.0
            # Solar world 290 standard values
            pv = Photovoltaic(environment, area=area, eta=0.161853,
                              temperature_nominal=46, alpha=-0.0041,
                              beta=angle)
            bes.addDevice(pv)

        if bat_list[i]:
            # TODO: Workaround for unstable implementation in pycity_base
            try:
                power_curve = bd.get_electric_power_curve()
            except Exception:
                power_curve = [0]
            if len(power_curve) == 0:
                power_curve = [0]
            capacity = max(power_curve)/1000.0
            bat = Battery(environment, E_El_Max=capacity, P_El_Max_Charge=4.6,
                          SOC_Ini=0.5, P_El_Max_Discharge=4.6)
            bes.addDevice(bat)

        buildings.append(bd)

    assert ap_counter == number_ap

    return buildings


def generate_tabula_district(environment,
                             number_sfh,
                             number_mfh,
                             sfh_building_distribution=None,
                             sfh_heating_distribution=None,
                             sfh_device_probabilities=None,
                             mfh_building_distribution=None,
                             mfh_heating_distribution=None,
                             mfh_device_probabilities=None,
                             agg_objective='price',
                             building_objective='price',
                             seed=1):
    """Create a TABULA district.

    Parameters
    ----------
    environment : pycity_scheduling.classes.Environment
    number_sfh : int
        Number of SFH buildings.
    number_mfh : int
        Number of MFH buildings.
    sfh_building_distribution : dict, optional
        The distribution of the houses among the tabula standard buildings. If
        omitted an equal distribution will be used.
        Keys : str
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    sfh_heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys : str
            {'HP', 'EH', 'CHP', 'BL'}
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    sfh_device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys : str
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values : float
            Number between 0 and 1.
    mfh_building_distribution : dict, optional
        The distribution of the houses among the tabula standard buildings. If
        omitted an equal distribution will be used.
        Keys : str
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    mfh_heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys : str
            {'HP', 'EH', 'CHP', 'BL'}
        Values : float
            Number between 0 and 1. The sum over all values must be one.
    mfh_device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys : str
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values : float
            Number between 0 and 1.
    agg_objective : str, optional
        Objective function for the aggregator. Defaults to 'price'.
    building_objective : str, optional
        Objective function for the buildings. Defaults to 'price'.
    seed: int, optional
        Specify a seed for the randomization. If omitted, a non-deterministic
        city district will be generated.

    Returns
    -------

    """
    cd = CityDistrict(environment, agg_objective)
    # noinspection PyListCreation
    building_list = []
    building_list.extend(generate_tabula_buildings(environment,
                                                   number_sfh,
                                                   sfh_building_distribution,
                                                   sfh_heating_distribution,
                                                   sfh_device_probabilities,
                                                   building_objective,
                                                   seed
                                                   ))
    building_list.extend(generate_tabula_buildings(environment,
                                                   number_mfh,
                                                   mfh_building_distribution,
                                                   mfh_heating_distribution,
                                                   mfh_device_probabilities,
                                                   building_objective,
                                                   seed+1,
                                                   ))
    positions = [Point(0, 0) for _ in building_list]
    cd.addMultipleEntities(building_list, positions)
    return cd


def generate_simple_building(env, fl=0, sh=0, eh=0, tes=0, bat=0):
    """Generate a simple building with loads and storages.

    Parameters
    ----------
    env : pycity_scheduling.classes.Environment
    fl : float, optional
        Demand of the FixedLoad in [kW].
    sh : float, optional
        Demand of the SpaceHeating in [kW].
    eh : float, optional
        Power of the ElectricHeater in [kW].
    tes : float, optional
        Capacity of the ThermalEnergyStorage in [kWh].
    bat : float, optional
        Capacity of the Battery in [kWh].

    Returns
    -------
    pycity_scheduling.classes.Building
    """
    ti = env.timer

    bd = Building(env)
    ap = Apartment(env)
    bd.addEntity(ap)
    bes = BuildingEnergySystem(env)
    bd.addEntity(bes)
    if fl:
        ap.addEntity(FixedLoad(env, demand=np.full(ti.simu_horizon, fl)))
    if sh:
        ap.addEntity(SpaceHeating(env, loadcurve=np.full(ti.simu_horizon, sh)))
    if eh:
        bes.addDevice(ElectricalHeater(env, P_Th_Nom=eh))
    if tes:
        bes.addDevice(ThermalEnergyStorage(env, E_Th_Max=tes, SOC_Ini=0.5))
    if bat:
        bes.addDevice(
            Battery(env, E_El_Max=bat, P_El_Max_Charge=bat/ti.time_slot)
        )
    return bd
