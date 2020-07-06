import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.demand.Apartment as apm

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from .entity_container import EntityContainer


class Apartment(EntityContainer, apm.Apartment):
    """
    Extension of pyCity_base class Apartment for scheduling purposes.
    """

    def __init__(self, environment, net_floor_area=None, occupancy=None):
        """Initialize apartment.

        Parameters
        ----------
        environment : Environment
            Common to all other objects. Includes time and weather instances
        net_floor_area : float, optional
            netto floor area in [m^2]
        occupancy : Occupancy, optional
        """
        super().__init__(environment, net_floor_area, occupancy)
        self._long_ID = "APM_" + self._ID_string

        self.Th_Demand_list = []
        self.El_Demand_list = []
        self.All_Demands_list = []

    def addEntity(self, entity):
        """Add entity to apartment.

        Parameters
        ----------
        entity : OptimizationEntitty
            Entitiy to be added to the apartment; must be of type FixedLoad,
            DeferrableLoad, CurtailableLoad, SpaceHeating or DomesticHotWater.
        """
        super(Apartment, self).addEntity(entity)

        if isinstance(entity, ThermalEntity):
            self.Th_Demand_list.append(entity)
        if isinstance(entity, ElectricalEntity):
            self.El_Demand_list.append(entity)
        self.All_Demands_list.append(entity)

    def get_lower_entities(self):
        yield from self.All_Demands_list
