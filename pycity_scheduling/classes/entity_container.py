import numpy as np
import pyomo.environ as pyomo

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class EntityContainer(ThermalEntity, ElectricalEntity):

    def populate_model(self, model, mode="convex"):
        """Add entity block and lower entities blocks to pyomo ConcreteModel.

        Call both parent's `populate_model` methods and set variables lower
        bounds to `None`. Then call `populate_model` method of all contained
        entities and add constraints that the sum of their variables for each
        period equals the corresponding own variable.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        m = self.model

        if mode in ["convex", "integer"]:
            P_Th_var_list = []
            P_El_var_list = []
            for entity in self.get_lower_entities():
                entity.populate_model(model, mode)
                if isinstance(entity, ThermalEntity):
                    P_Th_var_list.append(entity.model.P_Th_vars)
                if isinstance(entity, ElectricalEntity):
                    P_El_var_list.append(entity.model.P_El_vars)

            m.P_Th_vars.setlb(None)
            m.P_El_vars.setlb(None)

            def p_th_sum_rule(model, t):
                return model.P_Th_vars[t] == pyomo.quicksum(P_Th_var[t] for P_Th_var in P_Th_var_list)
            m.p_th_constr = pyomo.Constraint(m.t, rule=p_th_sum_rule)

            def p_el_sum_rule(model, t):
                return model.P_El_vars[t] == pyomo.quicksum(P_El_var[t] for P_El_var in P_El_var_list)
            m.p_el_constr = pyomo.Constraint(m.t, rule=p_el_sum_rule)
        else:
            raise ValueError(
                "Mode %s is not implemented by EntityContainer." % str(mode)
            )

    def update_model(self, mode=""):
        super().update_model(mode)
        for entity in self.get_lower_entities():
            entity.update_model(mode)

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        super().update_schedule()

        for entity in self.get_lower_entities():
            entity.update_schedule()

    def save_ref_schedule(self):
        """Save the current reference schedule."""
        super().save_ref_schedule()

        for entity in self.get_lower_entities():
            entity.save_ref_schedule()

    def reset(self, schedule=None):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : str, optional
            Name of schedule to reset.
            If None resets all schedules.
        """
        super().reset(schedule)

        for entity in self.get_lower_entities():
            entity.reset(schedule)

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
        raise NotImplementedError
