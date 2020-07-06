import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.BES as bes

from .entity_container import EntityContainer


class BuildingEnergySystem(EntityContainer, bes.BES):
    """
    Extension of pyCity_base class BES for scheduling purposes.
    """

    def __init__(self, environment):
        super().__init__(environment)
        self._long_ID = "BES_" + self._ID_string

    def get_lower_entities(self):
        if self.hasBoiler:
            yield self.boiler
        if self.hasChp:
            yield self.chp
        if self.hasElectricalHeater:
            yield self.electricalHeater
        if self.hasHeatpump:
            yield self.heatpump
        if self.hasTes:
            yield self.tes
        if self.hasBattery:
            yield self.battery
        if self.hasPv:
            yield self.pv
