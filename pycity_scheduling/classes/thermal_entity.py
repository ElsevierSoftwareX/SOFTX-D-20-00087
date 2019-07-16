import numpy as np
import gurobipy as gurobi

from .optimization_entity import OptimizationEntity


class ThermalEntity(OptimizationEntity):
    """
    Base class for all thermal entities derived from OptimizationEntity.

    This class provides functionalities common to all thermal entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super(ThermalEntity, self).__init__(environment, *args, **kwargs)

        self.P_Th_vars = []
        self.P_Th_Schedule = np.zeros(self.simu_horizon)
        self.P_Th_Act_Schedule = np.zeros(self.simu_horizon)
        self.P_Th_Ref_Schedule = np.zeros(self.simu_horizon)
        self.P_Th_Act_var = None

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
        self.P_Th_vars = []
        for t in self.op_time_vec:
            self.P_Th_vars.append(
                model.addVar(
                    name="%s_P_Th_at_t=%i" % (self._long_ID, t+1)
                )
            )
        model.update()

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        op_slice = self.op_slice
        self.P_Th_Schedule[op_slice] = [var.x for var in self.P_Th_vars]
        self.P_Th_Act_Schedule[op_slice] = self.P_Th_Schedule[op_slice]

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model."""
        self.P_Th_Act_var = model.addVar(
            name="%s_P_Th_Actual" % self._long_ID
        )

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        self.P_Th_Act_Schedule[timestep] = self.P_Th_Act_var.x

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        np.copyto(
            self.P_Th_Ref_Schedule,
            self.P_Th_Schedule
        )

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
        if schedule:
            self.P_Th_Schedule.fill(0)
        if actual:
            self.P_Th_Act_Schedule.fill(0)
        if reference:
            self.P_Th_Ref_Schedule.fill(0)
