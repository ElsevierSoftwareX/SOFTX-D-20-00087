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


from pycity_scheduling.classes.timer import Timer
from pycity_scheduling.classes.prices import Prices
from pycity_scheduling.classes.weather import Weather
from pycity_scheduling.classes.environment import Environment
from pycity_scheduling.classes.optimization_entity import OptimizationEntity
from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating
from pycity_scheduling.classes.thermal_entity_cooling import ThermalEntityCooling
from pycity_scheduling.classes.electrical_entity import ElectricalEntity
from pycity_scheduling.classes.city_district import CityDistrict
from pycity_scheduling.classes.building import Building
from pycity_scheduling.classes.building_energy_system import BuildingEnergySystem
from pycity_scheduling.classes.apartment import Apartment
from pycity_scheduling.classes.battery import Battery
from pycity_scheduling.classes.boiler import Boiler
from pycity_scheduling.classes.chiller import Chiller
from pycity_scheduling.classes.combined_heat_power import CombinedHeatPower
from pycity_scheduling.classes.curtailable_load import CurtailableLoad
from pycity_scheduling.classes.deferrable_load import DeferrableLoad
from pycity_scheduling.classes.electrical_heater import ElectricalHeater
from pycity_scheduling.classes.electrical_vehicle import ElectricalVehicle
from pycity_scheduling.classes.fixed_load import FixedLoad
from pycity_scheduling.classes.heat_pump import HeatPump
from pycity_scheduling.classes.photovoltaic import Photovoltaic
from pycity_scheduling.classes.space_cooling import SpaceCooling
from pycity_scheduling.classes.space_heating import SpaceHeating
from pycity_scheduling.classes.thermal_heating_storage import ThermalHeatingStorage
from pycity_scheduling.classes.thermal_cooling_storage import ThermalCoolingStorage
from pycity_scheduling.classes.wind_energy_converter import WindEnergyConverter


__all__ = [
    'Timer',
    'Prices',
    'Weather',
    'Environment',
    'OptimizationEntity',
    'ThermalEntityCooling',
    'ThermalEntityHeating',
    'ElectricalEntity',
    'CityDistrict',
    'Building',
    'BuildingEnergySystem',
    'Apartment',
    'Battery',
    'Boiler',
    'Chiller',
    'CombinedHeatPower',
    'CurtailableLoad',
    'DeferrableLoad',
    'ElectricalHeater',
    'ElectricalVehicle',
    'FixedLoad',
    'HeatPump',
    'Photovoltaic',
    'SpaceCooling',
    'SpaceHeating',
    'ThermalHeatingStorage',
    'ThermalCoolingStorage',
    'WindEnergyConverter',
    'all_entities',
    'heating_devices',
    'consumption_devices',
    'generation_devices',
    'storage_devices',
    'filter_entities',
]


all_entities = {
    'OE': OptimizationEntity,
    'TEC': ThermalEntityCooling,
    'TEH': ThermalEntityHeating,
    'EE': ElectricalEntity,
    'CD': CityDistrict,
    'BD': Building,
    'BES': BuildingEnergySystem,
    'AP': Apartment,
    'BAT': Battery,
    'BL': Boiler,
    'CH': Chiller,
    'CHP': CombinedHeatPower,
    'CL': CurtailableLoad,
    'DL': DeferrableLoad,
    'EH': ElectricalHeater,
    'EV': ElectricalVehicle,
    'FL': FixedLoad,
    'HP': HeatPump,
    'PV': Photovoltaic,
    'SC': SpaceCooling,
    'SH': SpaceHeating,
    'THS': ThermalHeatingStorage,
    'TCS': ThermalCoolingStorage,
    'WEC': WindEnergyConverter,
}

heating_devices = {
    'HP': HeatPump,
    'BL': Boiler,
    'CHP': CombinedHeatPower,
    'EH': ElectricalHeater,
}

cooling_devices = {
    'CH': Chiller,
}

consumption_devices = {
    'CL': CurtailableLoad,
    'DL': DeferrableLoad,
    'EV': ElectricalVehicle,
    'FL': FixedLoad,
}

generation_devices = {
    'CHP': CombinedHeatPower,
    'PV': Photovoltaic,
    'WEC': WindEnergyConverter,
}

storage_devices = {
    'BAT': Battery,
    'THS': ThermalHeatingStorage,
    'TCS': ThermalCoolingStorage,
}


def filter_entities(entities, entity_type):
    """
    Filter a list of entities for given entity types.

    Parameters
    ----------
    entities : list or generator or
               pycity_scheduling.classes.OptimizationEntity
        Entities to be filtered. When an Optimization Entity is given its
        `get_entities` method is called.
    entity_type : str or list or dict
        In case of `str`: must be the name of a dictionary from this module
                          (e.g. 'generation_devices') or the short name of an entity
                          (e.g. 'PV')
        In case of `list`: must be a list of classes to be filtered for or a
                           list of short names (e.g. `['PV', 'WEC']`)
        In case of `dict`: its values must be the classes to be filtered for

    Yields
    ------
    OptimizationEntity :
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
