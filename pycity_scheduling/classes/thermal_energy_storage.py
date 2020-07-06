import numpy as np
import pyomo.environ as pyomo

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

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method and set variables lower bounds
        to `None`. Then add variables for the state of charge with an upper
        bound of `self.E_Th_Max`. Also add continuity constraints to the model.

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

        if mode == "convex" or "integer":
            m.P_Th_vars.setlb(None)

            m.E_Th_vars = pyomo.Var(m.t, domain=pyomo.NonNegativeReals, bounds=(0, self.E_Th_Max), initialize=0)

            m.E_Th_ini = pyomo.Param(default=self.SOC_Ini * self.E_Th_Max, mutable=True)

            def e_rule(model, t):
                E_Th_last = model.E_Th_vars[t - 1] if t >= 1 else model.E_Th_ini
                return model.E_Th_vars[t] == E_Th_last * (1 - self.Th_Loss_coeff) + m.P_Th_vars[t] * self.time_slot
            m.E_constr = pyomo.Constraint(m.t, rule=e_rule)

            def e_end_rule(model):
                if self.storage_end_equality:
                    return model.E_Th_vars[self.op_horizon-1] == self.E_Th_Max * self.SOC_Ini
                else:
                    return model.E_Th_vars[self.op_horizon-1] >= self.E_Th_Max * self.SOC_Ini
            m.E_end_constr = pyomo.Constraint(rule=e_end_rule)

        else:
            raise ValueError(
                "Mode %s is not implemented by TES." % str(mode)
            )

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        if timestep == 0:
            m.E_Th_Ini = self.SOC_Ini * self.E_Th_Max
        else:
            m.E_Th_Ini = self.E_Th_Schedule[timestep-1]
