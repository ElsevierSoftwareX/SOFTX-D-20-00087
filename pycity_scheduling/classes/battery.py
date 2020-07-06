import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.Battery as bat

from .electrical_entity import ElectricalEntity


class Battery(ElectricalEntity, bat.Battery):
    """
    Extension of pyCity_base class Battery for scheduling purposes.
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
        super().__init__(environment, soc_abs, capacity, 0, eta, eta)
        self._long_ID = "BAT_" + self._ID_string

        self.objective = 'peak-shaving'
        self.E_El_Max = E_El_max
        self.SOC_Ini = soc_init  # relative SOC
        self.P_El_Max_Charge = P_El_max_charge
        self.P_El_Max_Discharge = P_El_max_discharge or P_El_max_charge
        self.storage_end_equality = storage_end_equality

        self.new_var("P_El_Demand")
        self.new_var("P_El_Supply")
        self.new_var("P_State", dtype=np.bool, func=lambda model, t: pyomo.value(
            model.P_El_Demand_vars[t] > model.P_El_Supply_vars[t]))
        self.new_var("E_El")

    def populate_model(self, model, mode="convex"):
        """Add device block of variables and constraints to pyomo ConcreteModel.

        Call parent's `populate_model` method and set variables lower bounds to
        `None`. Then add variables for demand, supply and the state of charge,
        with their corresponding upper bounds (`self.P_El_Max_Charge`,
        `self.P_El_Max_Discharge`, `self.E_El_Max`). Finally add continuity
        constraints to the block.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)
        m = self.model
        if mode in ["convex", "integer"]:
            # additional variables for battery
            m.P_El_vars.setlb(None)
            m.P_El_Demand_vars = pyomo.Var(m.t, domain=pyomo.NonNegativeReals,
                                           bounds=(0.0, np.inf if mode == "integer" else self.P_El_Max_Charge),
                                           initialize=0)
            m.P_El_Supply_vars = pyomo.Var(m.t, domain=pyomo.NonNegativeReals,
                                           bounds=(0.0, np.inf if mode == "integer" else self.P_El_Max_Discharge),
                                           initialize=0)
            m.E_El_vars = pyomo.Var(m.t, domain=pyomo.NonNegativeReals, bounds=(0, self.E_El_Max), initialize=0)

            def p_rule(model, t):
                return model.P_El_vars[t] == model.P_El_Demand_vars[t] - model.P_El_Supply_vars[t]
            m.P_constr = pyomo.Constraint(m.t, rule=p_rule)
            m.E_El_ini = pyomo.Param(default=self.SOC_Ini * self.E_El_Max, mutable=True)

            def e_rule(model, t):
                delta = (
                        (self.etaCharge * model.P_El_Demand_vars[t]
                         - (1 / self.etaDischarge) * model.P_El_Supply_vars[t])
                        * self.time_slot
                )
                E_El_last = model.E_El_vars[t - 1] if t >= 1 else model.E_El_ini
                return model.E_El_vars[t] == E_El_last + delta
            m.E_constr = pyomo.Constraint(m.t, rule=e_rule)

            def e_end_rule(model):
                if self.storage_end_equality:
                    return model.E_El_vars[self.op_horizon-1] == self.E_El_Max * self.SOC_Ini
                else:
                    return model.E_El_vars[self.op_horizon-1] >= self.E_El_Max * self.SOC_Ini
            m.E_end_constr = pyomo.Constraint(rule=e_end_rule)


            if mode == "integer":
                m.P_State_vars = pyomo.Var(m.t, domain=pyomo.Binary)
                def c_rule(model, t):
                    return model.P_El_Demand_vars[t] <= model.P_State_vars[t] * self.P_El_Max_Charge
                m.E_charge_constr = pyomo.Constraint(m.t, rule=c_rule)
                def d_rule(model, t):
                    return model.P_El_Supply_vars[t] <= (1 - model.P_State_vars[t]) * self.P_El_Max_Discharge
                m.E_discharge_constr = pyomo.Constraint(m.t, rule=d_rule)

        else:
            raise ValueError(
                "Mode %s is not implemented by battery." % str(mode)
            )

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        if timestep == 0:
            m.E_El_Ini = self.SOC_Ini * self.E_El_Max
        else:
            m.E_El_Ini = self.E_El_Schedule[timestep - 1]
