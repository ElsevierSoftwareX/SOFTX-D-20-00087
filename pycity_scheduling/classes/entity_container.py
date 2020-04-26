import gurobipy as gurobi

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class EntityContainer(ThermalEntity, ElectricalEntity):

    def populate_model(self, model, mode="convex"):
        """Add variables and constraints to Gurobi model.

        Call both parent's `populate_model` methods and set variables lower
        bounds to `-gurobi.GRB.INFINITY`. Then call `populate_model` method
        of all contained entities and add constraints that the sum of their
        variables for each period equals the corresponding own variable.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)

        if mode in ["convex", "integer"]:
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
                    "{0:s}_P_Th_at_t={1}".format(self._long_ID, t + 1)
                )
                model.addConstr(
                    self.P_El_vars[t] == P_El_var_sum,
                    "{0:s}_P_El_t={1}".format(self._long_ID, t + 1)
                )
        else:
            raise ValueError(
                "Mode %s is not implemented by EntityContainer." % str(mode)
            )

    def update_model(self, model, mode=""):
        super().update_model(model, mode)
        for entity in self.get_lower_entities():
            entity.update_model(model, mode)

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
        super().reset(self, schedule)

        for entity in self.get_lower_entities():
            entity.reset(schedule)

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
        raise NotImplementedError
