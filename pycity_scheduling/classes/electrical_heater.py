import gurobipy as gurobi
import pycity_base.classes.supply.ElectricalHeater as eh

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class ElectricalHeater(ThermalEntity, ElectricalEntity, eh.ElectricalHeater):
    """
    Extension of pyCity_base class ElectricalHeater for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, eta=1, lower_activation_limit=0):
        """Initialize ElectricalHeater.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal thermal power output in [kW].
        eta : float, optional
            Efficiency of the electrical heater.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the electrical heater
            as a percentage of the rated power. When the electrical heater is
            running its power nust be zero or between the lower activation
            limit and its rated power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        # Flow temperature of 55 C
        super().__init__(environment, P_Th_nom*1000, eta, 55, lower_activation_limit)
        self._long_ID = "EH_" + self._ID_string
        self.P_Th_Nom = P_Th_nom
        self.P_State_vars = []

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model.

        Call parent's `populate_model` method and set thermal variables upper
        bounds to `self.P_Th_Nom`. Also add constraint to bind electrical
        demand to thermal output.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)

        if mode == "convex" or "integer":
            for var in self.P_Th_vars:
                var.lb = -self.P_Th_Nom
                var.ub = 0

            for t in self.op_time_vec:
                model.addConstr(
                    - self.P_Th_vars[t] == self.eta * self.P_El_vars[t]
                )
            if mode == "integer" and self.lowerActivationLimit != 0.0:
                # Add additional binary variables representing operating state
                for t in self.op_time_vec:
                    self.P_State_vars.append(
                        model.addVar(
                            vtype=gurobi.GRB.BINARY,
                            name="%s_Mode_at_t=%i"
                                 % (self._long_ID, t + 1)
                        )
                    )
                model.update()

                for t in self.op_time_vec:
                    # Couple state to operating variable
                    model.addConstr(
                        self.P_Th_vars[t]
                        >= -self.P_State_vars[t] * self.P_Th_Nom
                    )
                    model.addConstr(
                        self.P_Th_vars[t]
                        <= -self.P_State_vars[t] * self.P_Th_Nom * self.lowerActivationLimit
                    )
                    # Remove redundant limits of P_Th_vars
                    self.P_Th_vars[t].lb = -gurobi.GRB.INFINITY
                    self.P_Th_vars[t].ub = gurobi.GRB.INFINITY
        else:
            raise ValueError(
                "Mode %s is not implemented by electrical heater." % str(mode)
            )

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds variables, sets the correct bounds to the thermal variable and
        adds a coupling constraint.
        """
        super().populate_deviation_model(model, mode)

        self.P_Th_Act_var.lb = -self.P_Th_Nom
        self.P_Th_Act_var.ub = 0
        model.addConstr(
            - self.P_Th_Act_var == self.eta * self.P_El_Act_var
        )
