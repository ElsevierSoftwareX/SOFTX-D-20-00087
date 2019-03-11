import numpy as np
import gurobipy as gurobi

from .electrical_entity import ElectricalEntity
from ..exception import PyCitySchedulingGurobiException


class BatteryEntity(ElectricalEntity):
    """
    Base class for all battery entities derived from ElectricalEntity.

    This class provides functionalities common to all battery like entities.
    """

    def __init__(self, timer, E_El_Max, SOC_Ini, SOC_End,
                 P_El_Max_Charge, P_El_Max_Discharge, *args, **kwargs):
        """Initialize BatteryEntity.

        Parameters
        ----------
        timer : Timer object
            Common Timer instance.
        E_El_Max : float
            Maximum electric capacity of the battery [kWh].
        SOC_Ini : float
            Initial state of charge.
        SOC_End : float
            Final state of charge.
        P_El_Max_Charge : float
            Maximum charging power [kW].
        P_El_Max_Discharge : float
            Maximum discharging power [kW].
        """
        super(BatteryEntity, self).__init__(timer, *args, **kwargs)

        self.E_El_Max = E_El_Max
        self.SOC_Ini = SOC_Ini
        self.SOC_End = SOC_End
        self.P_El_Max_Charge = P_El_Max_Charge
        self.P_El_Max_Discharge = P_El_Max_Discharge

        self.E_El_vars = []
        self.E_El_Init_constr = None
        self.E_El_Schedule = np.zeros(self.simu_horizon)
        self.P_El_Demand_vars = []
        self.P_El_Supply_vars = []
        self.E_El_Ref_Schedule = np.zeros(self.simu_horizon)

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model.

        Call parent's `populate_model` method and set variables lower bounds to
        `-gurobi.GRB.INFINITY`. Then add variables for demand, supply and the
        state of charge, with their corresponding upper bounds
        (`self.P_El_Max_Charge`, `self.P_El_Max_Discharge`, `self.E_El_Max`).
        Finally add continuity constraints to the model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(BatteryEntity, self).populate_model(model, mode)

        # additional variables for battery
        self.P_El_Demand_vars = []
        self.P_El_Supply_vars = []
        self.E_El_vars = []
        for t in self.op_time_vec:
            self.P_El_vars[t].lb = -gurobi.GRB.INFINITY
            self.P_El_Demand_vars.append(
                model.addVar(
                    ub=self.P_El_Max_Charge,
                    name="%s_E_El_Demand_at_t=%i"
                         % (self._long_ID, t + 1)
                )
            )
            self.P_El_Supply_vars.append(
                model.addVar(
                    ub=self.P_El_Max_Discharge,
                    name="%s_E_El_Supply_at_t=%i"
                         % (self._long_ID, t + 1)
                )
            )
            self.E_El_vars.append(
                model.addVar(
                    ub=self.E_El_Max,
                    name="%s_E_El_at_t=%i" % (self._long_ID, t + 1)
                )
            )
        model.update()

        for t in self.op_time_vec:
            model.addConstr(
                self.P_El_vars[t]
                == self.P_El_Demand_vars[t] - self.P_El_Supply_vars[t]
            )

    def update_schedule(self, mode=""):
        super(BatteryEntity, self).update_schedule(mode)
        timestep = self.timer.currentTimestep
        t = 0
        try:
            self.E_El_Schedule[timestep:timestep+self.op_horizon] \
                = [var.x for var in self.E_El_vars]
        except gurobi.GurobiError:
            self.E_El_Schedule[t:self.op_horizon + timestep].fill(0)
            raise PyCitySchedulingGurobiException(
                str(self) + ": Could not read from variables."
            )

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(BatteryEntity, self).save_ref_schedule()
        np.copyto(
            self.E_El_Ref_Schedule,
            self.E_El_Schedule
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
        super(BatteryEntity, self).reset(schedule, reference)

        if schedule:
            self.E_El_Schedule.fill(0)
        if reference:
            self.E_El_Ref_Schedule.fill(0)
