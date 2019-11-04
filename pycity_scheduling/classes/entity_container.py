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

    def populate_deviation_model(self, model, mode=""):
        """
        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        """
        super().populate_deviation_model(model, mode)

        P_Th_var_list = []
        P_El_var_list = []
        for entity in self.get_lower_entities():
            entity.populate_deviation_model(model, mode)
            if isinstance(entity, ThermalEntity):
                P_Th_var_list.append(entity.P_Th_Act_var)
            if isinstance(entity, ElectricalEntity):
                P_El_var_list.append(entity.P_El_Act_var)
        self.P_Th_Act_var.lb = -gurobi.GRB.INFINITY
        self.P_El_Act_var.lb = -gurobi.GRB.INFINITY
        P_Th_var_sum = gurobi.quicksum(P_Th_var_list)
        P_El_var_sum = gurobi.quicksum(P_El_var_list)
        model.addConstr(
            self.P_Th_Act_var == P_Th_var_sum,
            "{0:s}_P_Th_Act".format(self._long_ID)
        )
        model.addConstr(
            self.P_El_Act_var == P_El_var_sum,
            "{0:s}_P_El_Act".format(self._long_ID)
        )

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        super().update_deviation_model()
        for entity in self.get_lower_entities():
            entity.update_deviation_model(model, timestep, mode)

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        super().update_actual_schedule(self, timestep)

        for entity in self.get_lower_entities():
            entity.update_actual_schedule(timestep)

    def save_ref_schedule(self):
        """Save the current reference schedule."""
        super().save_ref_schedule()

        for entity in self.get_lower_entities():
            entity.save_ref_schedule()

    def reset(self, schedule=True, actual=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        actual : bool, optional
            Specify if to reset actual schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        super().reset(self, schedule, actual, reference)

        for entity in self.get_lower_entities():
            entity.reset(schedule, actual, reference)

    def get_lower_entities(self):
        """

        Yields
        ------
        All contained entities.
        """
        raise NotImplementedError
