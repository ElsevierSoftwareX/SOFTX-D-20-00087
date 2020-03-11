import numpy as np
import gurobipy as gurobi

from .optimization_entity import OptimizationEntity


class ThermalEntity(OptimizationEntity):
    """
    Base class for all thermal entities derived from OptimizationEntity.

    This class provides functionality common to all thermal entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("P_Th")

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model.

        Add variables for the thermal demand of the entity to the optimization
        model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        for t in self.op_time_vec:
            self.P_Th_vars.append(
                model.addVar(
                    name="%s_P_Th_at_t=%i" % (self._long_ID, t+1)
                )
            )
        model.update()

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        super().update_schedule()
        op_slice = self.op_slice
        self.P_Th_Act_Schedule[op_slice] = self.P_Th_Schedule[op_slice]

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model."""
        super().populate_deviation_model(model, mode)
        self.P_Th_Act_var = model.addVar(
            name="%s_P_Th_Actual" % self._long_ID
        )

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        super().update_actual_schedule(timestep)
        self.P_Th_Act_Schedule[timestep] = self.P_Th_Act_var.x
