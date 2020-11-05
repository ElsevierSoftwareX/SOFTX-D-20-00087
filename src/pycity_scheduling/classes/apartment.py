"""
The pycity_scheduling Framework


Institution:
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pycity_base.classes.demand.apartment as apm

from pycity_scheduling.classes.thermal_entity_cooling import ThermalEntityCooling
from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating
from pycity_scheduling.classes.electrical_entity import ElectricalEntity
from pycity_scheduling.classes.entity_container import EntityContainer


class Apartment(EntityContainer, apm.Apartment):
    """
    Extension of pyCity_base class Apartment for scheduling purposes.

    Parameters
    ----------
    environment : Environment
        Common to all other objects. Includes time and weather instances
    net_floor_area : float, optional
        netto floor area in [m^2]
    occupancy : Occupancy, optional
        Occupancy profile from pycity_base for the apartment.

    Notes
    -----
    - Apartments inherit their set of constraints from EntityContainer.
    """

    def __init__(self, environment, net_floor_area=None, occupancy=None):
        super().__init__(environment, net_floor_area, occupancy)
        self._long_id = "APM_" + self._id_string

        self.th_cooling_demand_list = []
        self.th_heating_demand_list = []
        self.el_demand_list = []
        self.all_demand_list = []

    def addEntity(self, entity):
        """
        Add entity to apartment.

        Parameters
        ----------
        entity : OptimizationEntity
            Entity to be added to the apartment; must be of type FixedLoad,
            DeferrableLoad, CurtailableLoad, SpaceHeating, SpaceCooling or DomesticHotWater.
        """
        super(Apartment, self).addEntity(entity)

        if isinstance(entity, ThermalEntityCooling):
            self.th_cooling_demand_list.append(entity)
        if isinstance(entity, ThermalEntityHeating):
            self.th_heating_demand_list.append(entity)
        if isinstance(entity, ElectricalEntity):
            self.el_demand_list.append(entity)
        self.all_demand_list.append(entity)
        return

    def get_lower_entities(self):
        yield from self.all_demand_list
