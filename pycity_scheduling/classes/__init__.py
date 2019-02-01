from .timer import Timer
from .prices import Prices
from .weather import Weather
from .environment import Environment
from .optimization_entity import OptimizationEntity
from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from .battery_entity import BatteryEntity
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
    "Timer",
    "Prices",
    "Weather",
    "Environment",
    "OptimizationEntity",
    "ThermalEntity",
    "ElectricalEntity",
    "BatteryEntity",
    "CityDistrict",
    "Building",
    "BuildingEnergySystem",
    "Apartment",
    "Battery",
    "Boiler",
    "CombinedHeatPower",
    "CurtailableLoad",
    "DeferrableLoad",
    "DomesticHotWater",
    "ElectricalHeater",
    "ElectricalVehicle",
    "FixedLoad",
    "HeatPump",
    "Photovoltaic",
    "SpaceHeating",
    "ThermalEnergyStorage",
    "WindEnergyConverter",
    "heating_devices"
]

heating_devices = {
    "HP": HeatPump,
    "BL": Boiler,
    "CHP": CombinedHeatPower,
    "EH": ElectricalHeater,
}
