import gurobipy as gurobi
import pycity_base.classes.supply.Boiler as bl

from .thermal_entity import ThermalEntity
from pycity_scheduling.constants import CO2_EMISSIONS_GAS


class Boiler(ThermalEntity, bl.Boiler):
    """
    Extension of pycity class Boiler for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, eta=1,
                 tMax=85, lowerActivationLimit=0):
        """Initialize Boiler.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_Nom : float
            Nominal heat output in [kW].
        eta : float, optional
            Efficiency.
        tMax : float, optional
            maximum provided temperature in [°C]
        lowerActivationLimit : float (0 <= lowerActivationLimit <= 1)
            Define the lower activation limit. For example, heat pumps are
            typically able to operate between 50 % part load and rated load.
            In this case, lowerActivationLimit would be 0.5
            Two special cases:
            Linear behavior: lowerActivationLimit = 0
            Two-point controlled: lowerActivationLimit = 1
        """
        super(Boiler, self).__init__(environment.timer, environment,
                                     1000*P_Th_Nom, eta, tMax,
                                     lowerActivationLimit)
        self._long_ID = "BL_" + self._ID_string

        self.P_Th_Nom = P_Th_Nom

    def populate_model(self, model, mode=""):
        """Add variables to Gurobi model

        Call parent's `populate_model` method and set variables upper bounds
        to `self.P_Th_Nom`.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(Boiler, self).populate_model(model, mode)

        for var in self.P_Th_vars:
            var.lb = -self.P_Th_Nom
            var.ub = 0

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the boiler wheighted with coeff.
        Sum of self.P_Th_vars.

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
            [- coeff] * self.op_horizon,
            self.P_Th_vars
        )
        return obj

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the Boiler.

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
        co2 = -(sum(p) * self.time_slot * CO2_EMISSIONS_GAS)
        return co2
