import numpy as np
import gurobipy as gurobi
import pycity_base.classes.supply.ThermalEnergyStorage as tes

from .thermal_entity import ThermalEntity


class ThermalEnergyStorage(ThermalEntity, tes.ThermalEnergyStorage):
    """
    Extension of pyCity_base class ThermalEnergyStorage for scheduling purposes.
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
        super().__init__(environment, 55, capacity, 55, 20, loss_factor)
        self._long_ID = "TES_" + self._ID_string

        self.E_Th_Max = E_Th_max
        self.SOC_Ini = soc_init
        self.storage_end_equality = storage_end_equality

        # TODO: very simple storage model which assumes tFlow == tSurroundings
        self.Th_Loss_coeff = (
            self.kLosses / self.capacity / self.cWater * self.time_slot * 3600
        )

        self.new_var("E_Th")
        self.E_Th_Init_constr = None

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
        super().populate_model(model, mode)

        if mode == "convex" or "integer":
            for var in self.P_Th_vars:
                var.lb = -gurobi.GRB.INFINITY

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
