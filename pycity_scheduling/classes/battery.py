import gurobipy as gurobi
import numpy as np
import pycity_base.classes.supply.Battery as bat

from .electrical_entity import ElectricalEntity
from pycity_scheduling.exception import PyCitySchedulingGurobiException


class Battery(ElectricalEntity, bat.Battery):
    """
    Extension of pycity class Battery for scheduling purposes
    """

    def __init__(self, environment, E_El_Max, P_El_Max_Charge,
                 P_El_Max_Discharge=None, SOC_Ini=0.5, eta=1,
                 storage_end_equality=False):
        """Initialize Battery.

        Parameters
        ----------
        environment : Environment object
            Common Environment instance.
        E_El_Max : float
            Electric capacity of the battery [kWh].
        P_El_Max_Charge : float
            Maximum charging power [kW].
        P_El_Max_Discharge : float
            Maximum discharging power [kW].
        SOC_Ini : float, optional
            Initial state of charge.
        eta : float, optional
            Charging and discharging efficiency. Must be in (0,1].
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        capacity = E_El_Max * 3600 * 1000
        soc_init = SOC_Ini * capacity  # absolute SOC
        super(Battery, self).__init__(environment.timer, environment, soc_init,
                                      capacity, 0, eta, eta)
        self._kind = "battery"
        self._long_ID = "BAT_" + self._ID_string

        self.E_El_Max = E_El_Max
        self.SOC_Ini = SOC_Ini  # relative SOC
        self.P_El_Max_Charge = P_El_Max_Charge
        self.P_El_Max_Discharge = P_El_Max_Discharge or P_El_Max_Charge
        self.storage_end_equality = storage_end_equality

        self.P_El_Demand_vars = []
        self.P_El_Supply_vars = []
        self.E_El_vars = []
        self.E_El_Init_constr = None
        self.E_El_coupl_constrs = []
        self.E_El_Schedule = np.zeros(self.simu_horizon)
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
        super(Battery, self).populate_model(model, mode)

        # additional variables for battery
        self.P_El_Demand_vars = []
        self.P_El_Supply_vars = []
        self.E_El_vars = []
        for t in self.op_time_vec:
            self.P_El_vars[t].lb = -gurobi.GRB.INFINITY
            self.P_El_Demand_vars.append(
                model.addVar(
                    ub=self.P_El_Max_Charge,
                    name="%s_P_El_Demand_at_t=%i"
                         % (self._long_ID, t + 1)
                )
            )
            self.P_El_Supply_vars.append(
                model.addVar(
                    ub=self.P_El_Max_Discharge,
                    name="%s_P_El_Supply_at_t=%i"
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
            # Need to be stored to enable removal by the Electric Vehicle
            model.addConstr(
                self.P_El_vars[t]
                == self.P_El_Demand_vars[t] - self.P_El_Supply_vars[t]
            )

        for t in range(1, self.op_horizon):
            delta = (
                (self.etaCharge * self.P_El_Demand_vars[t]
                 - (1/self.etaDischarge) * self.P_El_Supply_vars[t])
                * self.time_slot
            )
            self.E_El_coupl_constrs.append(model.addConstr(
                self.E_El_vars[t] == self.E_El_vars[t-1] + delta
            ))
        self.E_El_vars[-1].lb = self.E_El_Max * self.SOC_Ini
        if self.storage_end_equality:
            self.E_El_vars[-1].ub = self.E_El_Max * self.SOC_Ini

    def update_model(self, model, mode=""):
        # raises GurobiError if constraint is from a prior scheduling
        # optimization or not present
        try:
            model.remove(self.E_El_Init_constr)
        except gurobi.GurobiError:
            pass
        timestep = self.timer.currentTimestep
        if timestep == 0:
            E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            E_El_Ini = self.E_El_Schedule[timestep - 1]
        delta = (
            (self.etaCharge * self.P_El_Demand_vars[0]
             - (1 / self.etaDischarge) * self.P_El_Supply_vars[0])
            * self.time_slot
        )
        self.E_El_Init_constr = model.addConstr(
            self.E_El_vars[0] == E_El_Ini + delta
        )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the battery wheighted with coeff.
        Standard quadratic term.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        obj = gurobi.QuadExpr()
        obj.addTerms(
            [coeff] * self.op_horizon,
            self.P_El_vars,
            self.P_El_vars
        )
        return obj

    def update_schedule(self, mode=""):
        super(Battery, self).update_schedule(mode)
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
        super(Battery, self).save_ref_schedule()
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
        super(Battery, self).reset(schedule, reference)

        if schedule:
            self.E_El_Schedule.fill(0)
        if reference:
            self.E_El_Ref_Schedule.fill(0)
