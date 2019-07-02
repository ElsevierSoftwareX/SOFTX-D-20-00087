import gurobipy as gurobi
import pycity_base.classes.supply.ElectricalHeater as eh

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class ElectricalHeater(ThermalEntity, ElectricalEntity, eh.ElectricalHeater):
    """
    Extension of pycity class ElectricalHeater for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, eta=1,
                 tMax=85, lowerActivationLimit=0):
        """Initialize ElectricalHeater.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_Nom : float
            Nominal thermal power output in [kW].
        eta : float, optional
            Efficiency of the electrical heater.
        tMax : integer, optional
            maximum provided temperature in °C
        lowerActivationLimit : float (0 <= lowerActivationLimit <= 1)
            Define the lower activation limit. For example, heat pumps are
            typically able to operate between 50 % part load and rated load.
            In this case, lowerActivationLimit would be 0.5
            Two special cases:
            Linear behavior: lowerActivationLimit = 0
            Two-point controlled: lowerActivationLimit = 1
        """
        super(ElectricalHeater, self).__init__(environment.timer, environment,
                                               P_Th_Nom*1000, eta, tMax,
                                               lowerActivationLimit)
        self._long_ID = "EH_" + self._ID_string

    def populate_model(self, model, mode=""):
        """Add variables to Gurobi model.

        Call parent's `populate_model` method and set thermal variables upper
        bounds to `self.P_Th_Nom`. Also add constraint to bind electrical
        demand to thermal output.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        ThermalEntity.populate_model(self, model, mode)
        ElectricalEntity.populate_model(self, model, mode)

        for var in self.P_Th_vars:
            var.lb = -self.qNominal / 1000
            var.ub = 0

        for t in self.op_time_vec:
            model.addConstr(
                - self.P_Th_vars[t] == self.eta * self.P_El_vars[t]
            )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the electrical heater wheighted with
        coeff. Sum of self.P_El_vars.

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
