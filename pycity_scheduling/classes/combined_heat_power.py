import gurobi
import pycity_base.classes.supply.CHP as chp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity
from pycity_scheduling.constants import CO2_EMISSIONS_GAS


class CombinedHeatPower(ThermalEntity, ElectricalEntity, chp.CHP):
    """
    Extension of pycity class CHP for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, P_El_Nom, eta, tMax=85,
                 lowerActivationLimit=1):
        p_nominal = P_El_Nom / 1000
        q_nominal = P_Th_Nom / 1000
        super(CombinedHeatPower, self).__init__(environment.timer, environment,
                                                p_nominal, q_nominal, eta,
                                                tMax, lowerActivationLimit)
        self._long_ID = "CHP_" + self._ID_string

        self.P_Th_Nom = P_Th_Nom
        self.P_El_Nom = P_El_Nom

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
            var.lb = -self.P_Th_Nom
            var.ub = 0
        for var in self.P_El_vars:
            var.lb = -self.P_El_Nom
            var.ub = 0

        # original function
        # 'qubic' -> would not work with Gurobi
        # COP = [
        #     -0.2434*(self.P_Th_vars[t]/self.P_Th_Nom)**2
        #     +1.1856*(self.P_Th_vars[t]/self.P_Th_Nom)
        #     +0.0487
        #     for t in self.OP_TIME_VEC
        # ]
        # function linearised with quadratic regression over the interval
        # [0, 1]
        # COP = [
        #     0.9422 * self.P_Th_vars[t] * (1 / self.P_Th_Nom) + 0.0889
        #     for t in self.OP_TIME_VEC
        #     ]
        for t in self.OP_TIME_VEC:
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
            [coeff] * self.OP_HORIZON,
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

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the CombinedHeatPower.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        if reference:
            p = self.P_Th_Ref_Schedule
        else:
            p = self.P_Th_Schedule
        if timestep:
            p = p[:timestep]
        co2 = ElectricalEntity.calculate_co2(timestep, reference)
        co2 -= sum(p) * self.TIME_SLOT * CO2_EMISSIONS_GAS
        return co2
