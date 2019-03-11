import random

from shapely.geometry import Point

from pycity_scheduling.exception import PyCitySchedulingInitError
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
    dt = int(3600/timer.timeDiscretization)
    ev_time_ranges = [
        [1] * (24 * dt),
        [0] * (8 * dt) + [1] * (12 * dt) + [0] * (4 * dt),
        [1] * (12 * dt) + [0] * (12 * dt),
        [0] * (12 * dt) + [1] * (12 * dt),
        [1] * (10 * dt) + [0] * (12 * dt) + [1] * (2 * dt),
        [1] * (9 * dt) + [0] * (12 * dt) + [1] * (3 * dt),
        [1] * (8 * dt) + [0] * (12 * dt) + [1] * (4 * dt),
        [1] * (7 * dt) + [0] * (12 * dt) + [1] * (5 * dt),
        [1] * (6 * dt) + [0] * (12 * dt) + [1] * (6 * dt),
        [1] * (5 * dt) + [0] * (12 * dt) + [1] * (7 * dt),
    ]
    return ev_time_ranges


def _calculate_dl_times(timer):
    dt = int(3600 / timer.timeDiscretization)
    dl_time_ranges = [
        [1] * (8 * dt) + [0] * (16 * dt),
        [0] * (8 * dt) + [1] * (4 * dt) + [0] * (12 * dt),
        [0] * (12 * dt) + [1] * (4 * dt) + [0] * (8 * dt),
        [0] * (16 * dt) + [1] * (4 * dt) + [0] * (4 * dt),
        [0] * (20 * dt) + [1] * (4 * dt),
        [0] * (17 * dt) + [1] * (4 * dt) + [0] * (3 * dt),
        [0] * (7 * dt) + [1] * (4 * dt) + [0] * (13 * dt),
        [0] * (10 * dt) + [1] * (4 * dt) + [0] * (10 * dt),
        [0] * (2 * dt) + [1] * (4 * dt) + [0] * (18 * dt),
    ]
    return dl_time_ranges


def generate_tabula_buildings(environment,
                              number,
                              building_distribution=None,
                              heating_distribution=None,
                              device_probabilities=None,
                              objective='price',
                              seed=1):
    """
    Generates a building list based on available TABULA data from:
    http://www.episcope.eu/

    Heating units are automatically dimensioned and added to each building.
    A TES always covers the thermal energy demand of a building for at least
    two hours.

    Parameters
    ----------
    environment : Environment
    number : int
        Number of houses to be generated.
    building_distribution : dict, optional
        The distribution of the houses among the tabula standard buildings. If
        omitted an equal distribution will be used.
        Keys :
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values :
            Number between 0 and 1. The sum over all values must be one.
    heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys :
            {'HP', 'EH', 'CHP', 'BL'}
        Values :
            Number between 0 and 1. The sum over all values must be one.
    device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys :
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values :
            Number between 0 and 1.
    seed: int, optional
        Specify a seed for the randomization. If omitted, a non-deterministic
        city district will be generated.

    Returns
    ----------
    list of pycity_scheduling.classes.Building :
        List of generated buildings.
    """
    standard_devices = {'FL': 1, 'DL': 0, 'PV': 0, 'EV': 0, 'BAT': 0}

    if building_distribution is None:
        share = 1/len(tbd)
        building_distribution = {b: share for b in tbd}
    if heating_distribution is None:
        share = 1/len(heating_devices)
        heating_distribution = {d: share for d in heating_devices}
    if device_probabilities is None:
        device_probabilities = standard_devices

    building_dicts = []
    for building, share in building_distribution.items():
        building_dicts += [tbd[building]] * round(share * number)
    if len(building_dicts) != number:
        raise PyCitySchedulingInitError("Bad building distribution.")

    heating_list = []
    for heating, share in heating_distribution.items():
        heating_list += [heating_devices[heating]] * round(share * number)
    if len(heating_list) != number:
        raise PyCitySchedulingInitError("Bad heating distribution.")

    if any(map(lambda x: not 0 <= x <= 1, device_probabilities.values())):
        raise PyCitySchedulingInitError("Bad device probabilities")

    number_ap = sum(building['apartments'] for building in building_dicts)
    a = round(device_probabilities.get('FL', 0) * number_ap)
    b = number_ap - a
    fl_list = [True] * a + [False] * b
    a = round(device_probabilities.get('DL', 0) * number_ap)
    b = number_ap - a
    dl_list = [True] * a + [False] * b
    a = round(device_probabilities.get('EV', 0) * number_ap)
    b = number_ap - a
    ev_list = [True] * a + [False] * b

    a = round(device_probabilities.get('PV', 0) * number)
    b = number - a
    pv_list = [True] * a + [False] * b
    a = round(device_probabilities.get('BAT', 0) * number)
    b = number - a
    bat_list = [True] * a + [False] * b

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
                                    E_Min_Consumption=e_el, time=time)
                ap.addEntity(dl)

            if ev_list[ap_counter]:
                ev_data = random.choice(list(evd.values()))
                ev_charging_time = random.choice(ev_time_ranges)
                ev = ElectricalVehicle(environment,
                                       E_El_Max=ev_data['e_el_storage_max'],
                                       P_El_Max_Charge=ev_data['p_el_nom'],
                                       SOC_Ini=random.uniform(0.0, 0.5),
                                       SOC_End=ev_data['soc_max'],
                                       charging_time=ev_charging_time)
                ap.addEntity(ev)

            bd.addEntity(ap)
            ap_counter += 1

        # TODO: Workaround for unstable implementation in pycity_base
        power_curve = bd.get_space_heating_power_curve()
        if len(power_curve) == 0:
            power_curve = [0]
        p_th_max = max(power_curve)/1000.0 + 1.0
        heating_device = heating_list[i](environment, P_Th_Nom=p_th_max)
        tes = ThermalEnergyStorage(environment, capacity=2.0*p_th_max,
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
            #TODO: Workaround for unstable implementation in pycity_base
            try:
                power_curve = bd.get_electric_power_curve()
            except:
                power_curve = [0]
            if len(power_curve) == 0:
                power_curve = [0]
            capacity = max(power_curve)/1000.0
            bat = Battery(environment, SOC_Ini=0.5, SOC_End=0.5,
                          E_El_Max=capacity, P_El_Max_Charge=4.6,
                          P_El_Max_Discharge=4.6)
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
        Keys :
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values :
            Number between 0 and 1. The sum over all values must be one.
    sfh_heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys :
            {'HP', 'EH', 'CHP', 'BL'}
        Values :
            Number between 0 and 1. The sum over all values must be one.
    sfh_device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys :
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values :
            Number between 0 and 1.
    mfh_building_distribution : dict, optional
        The distribution of the houses among the tabula standard buildings. If
        omitted an equal distribution will be used.
        Keys :
            'DE.N.<SFH|MFH>.<n>.Gen' or '<SFH|MFH>.<year>'
        Values :
            Number between 0 and 1. The sum over all values must be one.
    mfh_heating_distribution : dict, optional
        The distribution of heating devices among the houses. If omitted an
        equal distribution will be used.
        Keys :
            {'HP', 'EH', 'CHP', 'BL'}
        Values :
            Number between 0 and 1. The sum over all values must be one.
    mfh_device_probabilities : dict, optional
        The probabilities of the houses / apartments to have the given device.
        Keys :
            {'FL', 'DL', 'EV', 'PV', 'BAT'}
        Values :
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
