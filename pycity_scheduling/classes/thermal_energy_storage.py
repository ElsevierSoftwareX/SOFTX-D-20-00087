import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.ThermalEnergyStorage as tes

from .thermal_entity import ThermalEntity


class ThermalEnergyStorage(ThermalEntity, tes.ThermalEnergyStorage):
    """
    Extension of pycity class ThermalEnergyStorage for scheduling purposes.
    """

    def __init__(self, environment, E_Th_max, soc_init=0.5, loss_factor=0,
                 storage_end_equality=False):
        """Initialize ThermalEnergyStorage.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        E_Th_max : float
            Amount of energy the TES is able to store in [kWh].
        soc_init : float
            Initial state of charge.
        loss_factor : float, optional
            Storage's loss factor (area*U_value) in [W/K].
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        # Room temperature of 20 C and flow temperature of 55 C
        capacity = E_Th_max / self.cWater / 35 * 3.6e6
        super(ThermalEnergyStorage, self).__init__(environment, 55, capacity,
                                                   55, 20, loss_factor)
        self._long_ID = "TES_" + self._ID_string

        self.E_Th_Max = E_Th_max
        self.SOC_Ini = soc_init
        self.storage_end_equality = storage_end_equality

        # TODO: very simple storage model which assumes tFlow == tSurroundings
        self.Th_Loss_coeff = (
            self.kLosses / self.capacity / self.cWater * self.time_slot * 3600
        )

        self.E_Th_vars = []
        self.E_Th_Init_constr = None
        self.E_Th_Schedule = np.zeros(self.simu_horizon)
        self.E_Th_Act_Schedule = np.zeros(self.simu_horizon)
        self.E_Th_Ref_Schedule = np.zeros(self.simu_horizon)
        self.E_Th_Act_var = None
        self.E_Th_Act_coupl_constr = None

    def populate_model(self, model, mode="convex"):
        """Add variables and constraints to Gurobi model

        Call parent's `populate_model` method and set variables lower bounds
        to `-gurobi.GRB.INFINITY`. Then add variables for the state of charge
        with an upper bound of `self.E_Th_Max`. Also add continuity constraints
        to the model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super(ThermalEnergyStorage, self).populate_model(model, mode)

        if mode == "convex" or "integer":
            for var in self.P_Th_vars:
                var.lb = -gurobi.GRB.INFINITY

            self.E_Th_vars = []
            for t in self.op_time_vec:
                self.E_Th_vars.append(
                    model.addVar(
                        ub=self.E_Th_Max,
                        name="%s_E_Th_at_t=%i" % (self._long_ID, t+1)
                    )
                )
            model.update()
            for t in range(1, self.op_horizon):
                model.addConstr(
                    self.E_Th_vars[t]
                    == self.E_Th_vars[t-1] * (1 - self.Th_Loss_coeff)
                       + self.P_Th_vars[t] * self.time_slot,
                    "{0:s}_P_Th_t={1}".format(self._long_ID, t)
                )
            self.E_Th_vars[-1].lb = self.E_Th_Max * self.SOC_Ini
            if self.storage_end_equality:
                self.E_Th_vars[-1].ub = self.E_Th_Max * self.SOC_Ini
        else:
            raise ValueError(
                "Mode %s is not implemented by TES." % str(mode)
            )

    def update_model(self, model, mode=""):
        timestep = self.timestep
        try:
            model.remove(self.E_Th_Init_constr)
        except gurobi.GurobiError:
            # raises GurobiError if constraint is from a prior scheduling
            # optimization or not present
            pass
        if timestep == 0:
            E_Th_Ini = self.SOC_Ini * self.E_Th_Max
        else:
            E_Th_Ini = self.E_Th_Schedule[timestep-1]
        self.E_Th_Init_constr = model.addConstr(
            self.E_Th_vars[0] == E_Th_Ini * (1 - self.Th_Loss_coeff)
                                 + self.P_Th_vars[0] * self.time_slot,
            "{0:s}_P_Th_t=0".format(self._long_ID)
        )

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        super(ThermalEnergyStorage, self).update_schedule()

        op_slice = self.op_slice
        self.E_Th_Schedule[op_slice] = [var.x for var in self.E_Th_vars]
        self.E_Th_Act_Schedule[op_slice] = self.E_Th_Schedule[op_slice]

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(ThermalEnergyStorage, self).save_ref_schedule()
        np.copyto(
            self.E_Th_Ref_Schedule,
            self.E_Th_Schedule
        )

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds a variable for the thermal power and energy. If `mode == 'full'`
        also adds a coupling constraint between them.
        """
        super().populate_deviation_model(model)

        self.P_Th_Act_var.lb = -gurobi.GRB.INFINITY
        self.E_Th_Act_var = model.addVar(
            ub=self.E_Th_Max,
            name="%s_E_Th_Actual" % self._long_ID
        )
        if mode == 'full':
            self.E_Th_Act_coupl_constr = model.addConstr(
                self.E_Th_Act_var - self.P_Th_Act_var * self.time_slot == 0

            )

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        if mode == 'full':
            if timestep == 0:
                E_Th_Ini = self.SOC_Ini * self.E_Th_Max
            else:
                E_Th_Ini = self.E_Th_Act_Schedule[timestep-1]
            self.E_Th_Act_coupl_constr.RHS = E_Th_Ini * (1-self.Th_Loss_coeff)
        else:
            self.P_Th_Act_var.lb = self.P_Th_Schedule[timestep]
            self.P_Th_Act_var.ub = self.P_Th_Schedule[timestep]
            self.E_Th_Act_var.lb = self.E_Th_Schedule[timestep]
            self.E_Th_Act_var.ub = self.E_Th_Schedule[timestep]

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        super().update_actual_schedule(timestep)

        self.E_Th_Act_Schedule[timestep] = self.E_Th_Act_var.x

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
        super(ThermalEnergyStorage, self).reset(schedule, actual, reference)

        if schedule:
            self.E_Th_Schedule.fill(0)
        if actual:
            self.E_Th_Act_Schedule.fill(0)
        if reference:
            self.E_Th_Ref_Schedule.fill(0)
