import gurobi
import pycity_base.classes.supply.ElectricalHeater as eh

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class ElectricalHeater(ThermalEntity, ElectricalEntity, eh.ElectricalHeater):
    """
    Extension of pycity class ElectricalHeater for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, eta=1,
                 tMax=85, lowerActivationLimit=1):
        super(ElectricalHeater, self).__init__(environment.timer, environment,
                                               P_Th_Nom, eta, tMax,
                                               lowerActivationLimit)
        self._long_ID = "EH_" + self._ID_string

        self.P_Th_Nom = P_Th_Nom

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
            var.lb = -self.P_Th_Nom
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

    def update_schedule(self, mode=""):
        ThermalEntity.update_schedule(self, mode)
        ElectricalEntity.update_schedule(self, mode)

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        ThermalEntity.save_ref_schedule(self)
        ElectricalEntity.save_ref_schedule(self)

    def reset(self, schedule=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        ThermalEntity.reset(self, schedule, reference)
        ElectricalEntity.reset(self, schedule, reference)
