import gurobi
import pycity_base.classes.demand.Apartment as apm

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class Apartment(ThermalEntity, ElectricalEntity, apm.Apartment):
    """
    Extension of pycity class Apartment for scheduling purposes
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
        super(Apartment, self).__init__(environment.timer,
                                        environment, net_floor_area, occupancy)
        self._long_ID = "APM_" + self._ID_string

        self.Th_Demand_list = []
        self.El_Demand_list = []
        self.All_Demands_list = []

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model.

        Call both parents' `populate_model` methods and set variables lower
        bounds to `-gurobi.GRB.INFINITY`. Then call `populate_model` method of
        all contained entities and add constraints that the sum of their
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
        for entity in self.Th_Demand_list:
            entity.populate_model(model, mode)
            P_Th_var_list.extend(entity.P_Th_vars)
        for entity in self.El_Demand_list:
            entity.populate_model(model, mode)
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
                "{0:s}_P_El_at_t={1}".format(self._long_ID, t)
            )

    def update_model(self, model, mode=""):
        for entity in self.All_Demands_list:
            entity.update_model(model, mode)

    def update_schedule(self, mode=""):
        ThermalEntity.update_schedule(self, mode)
        ElectricalEntity.update_schedule(self, mode)

        for entity in self.get_lower_entities():
            entity.update_schedule(mode)

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
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
