import gurobi
import pycity_base.classes.supply.BES as bes

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class BuildingEnergySystem(ThermalEntity, ElectricalEntity, bes.BES):
    """
    Extension of pycity class BES for scheduling purposes.
    """

    def __init__(self, environment):
        super(BuildingEnergySystem, self).__init__(environment.timer,
                                                   environment)
        self._long_ID = "BES_" + self._ID_string

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model.

        Call both parent's `populate_model` methods and set variables lower
        bounds to `-gurobi.GRB.INFINITY`. Then call `populate_model` method
        of all contained entities and add constraints that the sum of their
        variables for each period equals the corresponding own variable.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        ThermalEntity.populate_model(self, model, mode)
        ElectricalEntity.populate_model(self, model, mode)

        P_Th_var_list = []
        P_El_var_list = []
        for entity in self.get_lower_entities():
            entity.populate_model(model, mode)
            if isinstance(entity, ThermalEntity):
                P_Th_var_list.extend(entity.P_Th_vars)
            if isinstance(entity, ElectricalEntity):
                P_El_var_list.extend(entity.P_El_vars)

        for t in self.op_time_vec:
            self.P_Th_vars[t].lb = -gurobi.GRB.INFINITY
            self.P_El_vars[t].lb = -gurobi.GRB.INFINITY
            P_Th_var_sum = gurobi.quicksum(P_Th_var_list[t::self.op_horizon])
            P_El_var_sum = gurobi.quicksum(P_El_var_list[t::self.op_horizon])
            model.addConstr(
                self.P_Th_vars[t] == P_Th_var_sum,
                "{0:s}_P_Th_at_t={1}".format(self._long_ID, t)
            )
            model.addConstr(
                self.P_El_vars[t] == P_El_var_sum,
                "{0:s}_P_El_t={1}".format(self._long_ID, t)
            )

    def update_model(self, model, mode=""):
        for entity in self.get_lower_entities():
            entity.update_model(model, mode)

    def update_schedule(self, mode=""):
        ThermalEntity.update_schedule(self, mode)
        ElectricalEntity.update_schedule(self, mode)
        for entity in self.get_lower_entities():
            entity.update_schedule()

    def save_ref_schedule(self):
        """Save the current reference schedule."""
        ThermalEntity.save_ref_schedule(self)
        ElectricalEntity.save_ref_schedule(self)

        for entity in self.get_lower_entities():
            entity.save_ref_schedule()

    def reset(self, schedule=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        ThermalEntity.reset(self, schedule, reference)
        ElectricalEntity.reset(self, schedule, reference)

        for entity in self.get_lower_entities():
            entity.reset(schedule, reference)

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the BuldingEnergySystem.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        co2 = 0
        for entity in self.get_lower_entities():
            co2 += entity.calculate_co2(timestep, reference)
        return co2

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
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

    def get_heating_entities(self):
        """Yields
        ------
        All contianed heating devices.
        """
        if self.hasBoiler:
            yield self.boiler
        if self.hasChp:
            yield self.chp
        if self.hasElectricalHeater:
            yield self.electricalHeater
        if self.hasHeatpump:
            yield self.heatpump
