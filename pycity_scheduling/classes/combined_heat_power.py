import gurobipy as gurobi
import pycity_base.classes.supply.CHP as chp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class CombinedHeatPower(ThermalEntity, ElectricalEntity, chp.CHP):
    """
    Extension of pycity class CHP for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, P_El_nom=None, eta=1,
                 lower_activation_limit=0):
        """Initialize CombinedHeatPower.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal thermal power output in [kW].
        P_El_nom : float, optional
            Nominal electrical power output in [kW]. Defaults to `P_Th_nom`.
        eta : float, optional
            Total efficiency of the CHP.
        lower_activation_limit : float, optional (only adhered to in integer mode)
            Must be in [0, 1]. Lower activation limit of the CHP as a
            percentage of the rated power. When the CHP is running its power
            must be zero or between the lower activation limit and its rated
            power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        q_nominal = P_Th_nom * 1000
        if P_El_nom is None:
            p_nominal = q_nominal
        else:
            p_nominal = P_El_nom * 1000
        # Flow temperature of 55 C
        super(CombinedHeatPower, self).__init__(environment, p_nominal,
                                                q_nominal, eta, 55,
                                                lower_activation_limit)
        self._long_ID = "CHP_" + self._ID_string
        self.P_Th_Nom = P_Th_nom
        self.P_State_vars = []

    def populate_model(self, model, mode="convex"):
        """Add variables and constraints to Gurobi model.

        Call both parents' `populate_model` methods and set the upper bounds
        of the thermal variables to `self.P_Th_Nom`, the lower bounds of the
        electrical variables to `-self.P_El_Nom` and the upper bounds to zero.
        Also add constraints to bind electrical demand to thermal output.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        ThermalEntity.populate_model(self, model, mode)
        ElectricalEntity.populate_model(self, model, mode)

        if mode == "convex" or mode == "integer":
            for var in self.P_Th_vars:
                var.lb = -self.P_Th_Nom
                var.ub = 0
            for var in self.P_El_vars:
                var.lb = -self.P_Th_Nom
                var.ub = 0

        # original function
        # 'qubic' -> would not work with Gurobi
        # COP = [
        #     -0.2434*(self.P_Th_vars[t]/self.P_Th_Nom)**2
        #     +1.1856*(self.P_Th_vars[t]/self.P_Th_Nom)
        #     +0.0487
        #     for t in self.op_time_vec
        # ]
        # function linearised with quadratic regression over the interval
        # [0, 1]
        # COP = [
        #     0.9422 * self.P_Th_vars[t] * (1 / self.P_Th_Nom) + 0.0889
        #     for t in self.op_time_vec
        #     ]

            for t in self.op_time_vec:
                model.addConstr(
                    self.P_Th_vars[t] * self.sigma == self.P_El_vars[t]
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
                        self.P_Th_vars[t][t]
                        >= -self.P_State_vars[t] * self.P_Th_Nom
                    )
                    model.addConstr(
                        self.P_Th_vars[t][t]
                        <= -self.P_State_vars[t] * self.P_Th_Nom * self.lowerActivationLimit
                    )
                    # Remove redundant limits of P_Th_vars
                    self.P_Th_vars[t].lb = -gurobi.GRB.INFINITY
                    self.P_Th_vars[t].ub = gurobi.GRB.INFINITY
        else:
            raise ValueError(
                "Mode %s is not implemented by CHP." % str(mode)
            )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the CHP wheighted with coeff.
        Sum of `self.P_El_vars`.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.LinExpr :
            Objective function.
        """
        obj = gurobi.LinExpr()
        obj.addTerms(
            [coeff] * self.op_horizon,
            self.P_El_vars
        )
        return obj

    def update_schedule(self):
        """Update the schedule with the scheduling model solution."""
        ThermalEntity.update_schedule(self)
        ElectricalEntity.update_schedule(self)

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds variables, sets the correct bounds to the thermal and electric
        variables and adds a coupling constraint.
        """
        ThermalEntity.populate_deviation_model(self, model, mode)
        ElectricalEntity.populate_deviation_model(self, model, mode)

        self.P_Th_Act_var.lb = -self.P_Th_Nom
        self.P_Th_Act_var.ub = 0
        model.addConstr(
            self.P_Th_Act_var * self.sigma == self.P_El_Act_var
        )

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution."""
        ThermalEntity.update_actual_schedule(self, timestep)
        ElectricalEntity.update_actual_schedule(self, timestep)

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        ThermalEntity.save_ref_schedule(self)
        ElectricalEntity.save_ref_schedule(self)

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
        ThermalEntity.reset(self, schedule, actual, reference)
        ElectricalEntity.reset(self, schedule, actual, reference)
