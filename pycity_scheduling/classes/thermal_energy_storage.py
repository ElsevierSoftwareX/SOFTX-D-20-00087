import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.ThermalEnergyStorage as tes

from .thermal_entity import ThermalEntity
from ..exception import PyCitySchedulingGurobiException


class ThermalEnergyStorage(ThermalEntity, tes.ThermalEnergyStorage):
    """
    Extension of pycity class ThermalEnergyStorage for scheduling purposes.
    """

    def __init__(self, environment, capacity, SOC_Ini, SOC_End=None,
                 tMax=60, tSurroundings=20, kLosses=0,
                 storage_end_equality=False):
        """Initialize ThermalEnergyStorage.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        capacity : int
            Storage mass in [kg].
        SOC_Ini : float
            Initial state of charge.
        SOC_End : float, optional
            Final state of charge.
        tMax : float, optional
            Maximum storage temperature in [°C].
        tSurroundings : float, optional
            Temperature of the storage's surroundings in [°C].
        kLosses : float, optional
            Storage's loss factor (area*U_value) in [W/K].
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        tInit = SOC_Ini * (tMax - tSurroundings) + tSurroundings
        super(ThermalEnergyStorage, self).__init__(
            environment.timer, environment, tInit,
            capacity, tMax, tSurroundings, kLosses
        )
        self._long_ID = "TES_" + self._ID_string

        self.E_Th_Max = capacity * self.cWater * (tMax - tSurroundings) / 3.6e6
        self.SOC_Ini = SOC_Ini
        if SOC_End is None:
            SOC_End = SOC_Ini
        self.SOC_End = SOC_End
        self.storage_end_equality = storage_end_equality

        # TODO: very simple storage model which assumes tFlow == tSurroundings
        self.Th_Loss_coeff = (
                self.kLosses / self.capacity / self.cWater * self.time_slot * 3600
        )

        self.E_Th_vars = []
        self.E_Th_Init_constr = None
        self.E_Th_Schedule = np.zeros(self.simu_horizon)
        self.E_Th_Ref_Schedule = np.zeros(self.simu_horizon)

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model

        Call parent's `populate_model` method and set variables lower bounds
        to `-gurobi.GRB.INFINITY`. Then add variables for the state of charge
        with an upper bound of `self.E_Th_Max`. Also add continuity constraints
        to the model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(ThermalEnergyStorage, self).populate_model(model, mode)
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
        self.E_Th_vars[-1].lb = self.E_Th_Max * self.SOC_End
        if self.storage_end_equality:
            self.E_Th_vars[-1].ub = self.E_Th_Max * self.SOC_End

    def update_model(self, model, mode=""):
        timestep = self.timer.currentTimestep
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

    def update_schedule(self, mode=""):
        super(ThermalEnergyStorage, self).update_schedule(mode)
        timestep = self.timer.currentTimestep
        t = 0
        try:
            self.E_Th_Schedule[timestep:timestep+self.op_horizon] \
                = [var.x for var in self.E_Th_vars]
        except gurobi.GurobiError:
            self.E_Th_Schedule[t:timestep+self.op_horizon].fill(0)
            raise PyCitySchedulingGurobiException(
                str(self) + ": Could not read from variables."
            )

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(ThermalEnergyStorage, self).save_ref_schedule()
        np.copyto(
            self.E_Th_Ref_Schedule,
            self.E_Th_Schedule
        )

    def reset(self, schedule=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        super(ThermalEnergyStorage, self).reset(schedule, reference)

        if schedule:
            self.E_Th_Schedule.fill(0)
        if reference:
            self.E_Th_Ref_Schedule.fill(0)

    def compute_flexibility(self):
        R_Flex = sum(
            abs(e - self.E_Th_Max*self.SOC_Ini)
            for e in self.E_Th_Schedule
        )
        r_Flex = R_Flex / sum(
            abs(e - self.E_Th_Max*self.SOC_Ini)
            for e in self.E_Th_Ref_Schedule
        )
        R_ResFlex = sum(
            max(e, e - self.E_Th_Max)
            for e in self.E_Th_Schedule
        )
        R_ref = sum(
            max(e, e - self.E_Th_Max)
            for e in self.E_Th_Schedule
        )
        r_ResFlex = (R_Flex - R_ref) / R_ref

        return R_Flex, r_Flex, R_ResFlex, r_ResFlex
