import gurobipy as gurobi
import pycity_base.classes.supply.CHP as chp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class CombinedHeatPower(ThermalEntity, ElectricalEntity, chp.CHP):
    """
    Extension of pyCity_base class CHP for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, P_El_Nom=None, eta=1, tMax=85,
                 lowerActivationLimit=0):
        """Initialize CombinedHeatPower.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_Nom : float
            Nominal thermal power output in [kW].
        P_El_Nom : float, optional
            Nominal electrical power output in [kW]. Defaults to `P_Th_Nom`.
        eta : float, optional
            Total efficiency of the CHP.
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
        q_nominal = P_Th_Nom * 1000
        if P_El_Nom is None:
            p_nominal = q_nominal
        else:
            p_nominal = P_El_Nom * 1000
        super(CombinedHeatPower, self).__init__(environment.timer, environment,
                                                p_nominal, q_nominal, eta,
                                                tMax, lowerActivationLimit)
        self._long_ID = "CHP_" + self._ID_string

    def populate_model(self, model, mode=""):
        """Add variables and constraints to Gurobi model.

        Call both parents' `populate_model` methods and set the upper bounds
        of the thermal variables to `self.P_Th_Nom`, the lower bounds of the
        electrical variables to `-self.P_El_Nom` and the upper bounds to zero.
        Also add constraints to bind electrical demand to thermal output.

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
        for var in self.P_El_vars:
            var.lb = -self.pNominal / 1000
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
