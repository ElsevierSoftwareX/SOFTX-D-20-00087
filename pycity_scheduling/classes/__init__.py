from .timer import Timer
from .prices import Prices
from .weather import Weather
from .environment import Environment
from .optimization_entity import OptimizationEntity
from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from .city_district import CityDistrict
from .building import Building
from .building_energy_system import BuildingEnergySystem
from .apartment import Apartment
from .battery import Battery
from .boiler import Boiler
from .combined_heat_power import CombinedHeatPower
from .curtailable_load import CurtailableLoad
from .deferrable_load import DeferrableLoad
from .domestic_hot_water import DomesticHotWater
from .electrical_heater import ElectricalHeater
from .electrical_vehicle import ElectricalVehicle
from .fixed_load import FixedLoad
from .heat_pump import HeatPump
from .photovoltaic import Photovoltaic
from .space_heating import SpaceHeating
from .thermal_energy_storage import ThermalEnergyStorage
from .wind_energy_converter import WindEnergyConverter

__all__ = [
    'Timer',
    'Prices',
    'Weather',
    'Environment',
    'OptimizationEntity',
    'ThermalEntity',
    'ElectricalEntity',
    'CityDistrict',
    'Building',
    'BuildingEnergySystem',
    'Apartment',
    'Battery',
    'Boiler',
    'CombinedHeatPower',
    'CurtailableLoad',
    'DeferrableLoad',
    'DomesticHotWater',
    'ElectricalHeater',
    'ElectricalVehicle',
    'FixedLoad',
    'HeatPump',
    'Photovoltaic',
    'SpaceHeating',
    'ThermalEnergyStorage',
    'WindEnergyConverter',
    'all_entities',
    'heating_devices',
    'res_devices',
    'filter_entities',
]


all_entities = {
    'OE': OptimizationEntity,
    'TE': ThermalEntity,
    'EE': ElectricalEntity,
    'CD': CityDistrict,
    'BD': Building,
    'BES': BuildingEnergySystem,
    'AP': Apartment,
    'BAT': Battery,
    'BL': Boiler,
    'CHP': CombinedHeatPower,
    'CL': CurtailableLoad,
    'DL': DeferrableLoad,
    'DHW': DomesticHotWater,
    'EH': ElectricalHeater,
    'EV': ElectricalVehicle,
    'FL': FixedLoad,
    'HP': HeatPump,
    'PV': Photovoltaic,
    'SH': SpaceHeating,
    'TES': ThermalEnergyStorage,
    'WEC': WindEnergyConverter,
}

heating_devices = {
    'HP': HeatPump,
    'BL': Boiler,
    'CHP': CombinedHeatPower,
    'EH': ElectricalHeater,
}

res_devices = {
    'CHP': CombinedHeatPower,
    'PV': Photovoltaic,
    'WEC': WindEnergyConverter,
}


def filter_entities(entities, entity_type):
    """Filter a list of entities for given entity types.

    Parameters
    ----------
    entities : list or generator or
               pycity_scheduling.classes.OptimizationEntity
        Entities to be filtered. When an Optimization Entity is given its
        `get_entities` method is called.
    entity_type : str or list or dict
        In case of `str`: must be the name of a dictionary from this module
                          (e.g. 'res_devices') or the short name of an entity
                          (e.g. 'PV')
        In case of `list`: must be a list of classes to be filtered for or a
                           list of short names (e.g. `['PV', 'WEC']`)
        In case of `dict`: its values must be the classes to be filtered for

    Yields
    ------
    OptimizationEnitity :
        All entities matching the given filter
    """
    if isinstance(entities, OptimizationEntity):
        entities = entities.get_entities()

    if isinstance(entity_type, str):
        if entity_type in all_entities:
            entity_type = [all_entities[entity_type]]
        elif entity_type in __all__:
            entity_type = eval(entity_type)
        else:
            raise ValueError
    if isinstance(entity_type, list):
        if isinstance(entity_type[0], str):
            cls_list = tuple(all_entities[e] for e in entity_type)
        elif issubclass(entity_type[0], OptimizationEntity):
            cls_list = tuple(entity_type)
        else:
            raise ValueError()
    elif isinstance(entity_type, dict):
        cls_list = tuple(entity_type.values())
    else:
        raise ValueError()

    for e in entities:
        if isinstance(e, cls_list):
            yield e
