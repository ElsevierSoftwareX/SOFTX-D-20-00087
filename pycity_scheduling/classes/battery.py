import gurobipy as gurobi
import numpy as np
import pycity_base.classes.supply.Battery as bat

from .electrical_entity import ElectricalEntity


class Battery(ElectricalEntity, bat.Battery):
    """
    Extension of pycity class Battery for scheduling purposes
    """

    def __init__(self, environment, E_El_max, P_El_max_charge,
                 P_El_max_discharge=None, soc_init=0.5, eta=1,
                 storage_end_equality=False):
        """Initialize Battery.

        Parameters
        ----------
        environment : Environment object
            Common Environment instance.
        E_El_max : float
            Electric capacity of the battery [kWh].
        P_El_max_charge : float
            Maximum charging power [kW].
        P_El_max_discharge : float
            Maximum discharging power [kW].
        soc_init : float, optional
            Initial state of charge.
        eta : float, optional
            Charging and discharging efficiency. Must be in (0,1].
        storage_end_equality : bool, optional
            `True` if the soc at the end of the scheduling has to be equal to
            the inintial soc.
            `False` if it has to be greater or equal than the initial soc.
        """
        capacity = E_El_max * 3600 * 1000
        soc_abs = soc_init * capacity  # absolute SOC
        super(Battery, self).__init__(environment, soc_abs,
                                      capacity, 0, eta, eta)
        self._long_ID = "BAT_" + self._ID_string

        self.E_El_Max = E_El_max
        self.SOC_Ini = soc_init  # relative SOC
        self.P_El_Max_Charge = P_El_max_charge
        self.P_El_Max_Discharge = P_El_max_discharge or P_El_max_charge
        self.storage_end_equality = storage_end_equality

        self.P_El_Demand_vars = []
        self.P_El_Supply_vars = []
        self.P_State_vars = []
        self.E_El_vars = []
        self.E_El_Init_constr = None
        self.E_El_coupl_constrs = []
        self.E_El_Schedule = np.zeros(self.simu_horizon)
        self.E_El_Act_Schedule = np.zeros(self.simu_horizon)
        self.E_El_Ref_Schedule = np.zeros(self.simu_horizon)
        self.P_El_Act_Demand_var = None
        self.P_El_Act_Supply_var = None
        self.E_El_Act_var = None
        self.E_El_Act_coupl_constr = None

    def populate_model(self, model, mode="convex"):
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
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super(Battery, self).populate_model(model, mode)
        if mode == "convex" or mode == "integer":
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

            if mode == "integer":
                # Add additional binary variables representing dis-/charging state
                for t in self.op_time_vec:
                    self.P_State_vars.append(
                        model.addVar(
                            vtype=gurobi.GRB.BINARY,
                            name="%s_P_Mode_at_t=%i"
                                 % (self._long_ID, t + 1)
                        )
                    )
                model.update()
                for t in self.op_time_vec:
                    # Couple state to discharging and charging variables
                    model.addConstr(
                        self.P_El_Demand_vars[t]
                        <= self.P_State_vars[t] * self.P_El_Max_Charge
                    )
                    model.addConstr(
                        self.P_El_Supply_vars[t]
                        <= (1 - self.P_State_vars[t]) * self.P_El_Max_Discharge
                    )
                    # Remove redundant ub of P_El_Demand_vars and P_El_Supply_vars
                    self.P_El_Demand_vars[t].ub = gurobi.GRB.INFINITY
                    self.P_El_Supply_vars[t].ub = gurobi.GRB.INFINITY

        else:
            raise ValueError(
                "Mode %s is not implemented by battery." % str(mode)
            )

    def update_model(self, model, mode=""):
        # raises GurobiError if constraint is from a prior scheduling
        # optimization or not present
        try:
            model.remove(self.E_El_Init_constr)
        except gurobi.GurobiError:
            pass
        timestep = self.timestep
        if timestep == 0:
            E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            E_El_Ini = self.E_El_Act_Schedule[timestep - 1]
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

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        super(Battery, self).update_schedule()

        op_slice = self.op_slice
        self.E_El_Schedule[op_slice] = [var.x for var in self.E_El_vars]
        self.E_El_Act_Schedule[op_slice] = self.E_El_Schedule[op_slice]

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds a variable for the electric demand, supply and energy. If
        `mode == 'full'` also adds a coupling constraint between them.
        """
        self.P_El_Act_Demand_var = model.addVar(
            ub=self.P_El_Max_Charge,
            name="%s_P_El_Actual_Demand" % self._long_ID
        )
        self.P_El_Act_Supply_var = model.addVar(
            ub=self.P_El_Max_Discharge,
            name="%s_P_El_Actual_Supply" % self._long_ID
        )
        self.E_El_Act_var = model.addVar(
            ub=self.E_El_Max,
            name="%s_E_El_Actual" % self._long_ID
        )
        if mode == 'full':
            delta = (
                (self.etaCharge * self.P_El_Act_Demand_var
                 - (1 / self.etaDischarge) * self.P_El_Act_Supply_var)
                * self.time_slot
            )
            self.E_El_Act_coupl_constr = model.addConstr(
                self.E_El_Act_var - delta == 0
            )

    def update_deviation_model(self, model, timestep, mode=""):
        """Update the deviation model for the current timestep."""
        if mode == 'full':
            if timestep == 0:
                E_El_Ini = self.SOC_Ini * self.E_El_Max
            else:
                E_El_Ini = self.E_El_Act_Schedule[timestep-1]
            self.E_El_Act_coupl_constr.RHS = E_El_Ini
        else:
            demand = max(self.P_El_Schedule[timestep], 0)
            supply = -min(self.P_El_Schedule[timestep], 0)
            self.P_El_Act_Demand_var.lb = demand
            self.P_El_Act_Demand_var.ub = demand
            self.P_El_Act_Supply_var.lb = supply
            self.P_El_Act_Supply_var.ub = supply
            self.E_El_Act_var.lb = self.E_El_Schedule[timestep]
            self.E_El_Act_var.ub = self.E_El_Schedule[timestep]

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        self.P_El_Act_Schedule[timestep] = (self.P_El_Act_Demand_var.x
                                            - self.P_El_Act_Supply_var.x)
        self.E_El_Act_Schedule[timestep] = self.E_El_Act_var.x

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        super(Battery, self).save_ref_schedule()
        np.copyto(
            self.E_El_Ref_Schedule,
            self.E_El_Schedule
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
        super(Battery, self).reset(schedule, reference)

        if schedule:
            self.E_El_Schedule.fill(0)
        if actual:
            self.E_El_Act_Schedule.fill(0)
        if reference:
            self.E_El_Ref_Schedule.fill(0)
