import gurobipy as gurobi
import pycity_base.classes.supply.Boiler as bl

from pycity_scheduling import constants, util
from .thermal_entity import ThermalEntity


class Boiler(ThermalEntity, bl.Boiler):
    """
    Extension of pycity class Boiler for scheduling purposes.
    """

    def __init__(self, environment, P_Th_nom, eta=1, lower_activation_limit=0):
        """Initialize Boiler.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_nom : float
            Nominal heat output in [kW].
        eta : float, optional
            Efficiency.
        lower_activation_limit : float, optional
            Must be in [0, 1]. Lower activation limit of the boiler as a
            percentage of the rated power. When the boiler is running its
            power nust be zero or between the lower activation limit and its
            rated power.
            `lower_activation_limit = 0`: Linear behavior
            `lower_activation_limit = 1`: Two-point controlled
        """
        # Flow temperature of 55 C
        super(Boiler, self).__init__(environment, 1000*P_Th_nom, eta,
                                     55, lower_activation_limit)
        self._long_ID = "BL_" + self._ID_string
        self.P_Th_Nom = P_Th_nom

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

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        if mode == 'full':
            self.P_Th_Act_var.lb = -self.P_Th_Nom
            self.P_Th_Act_var.ub = 0
        else:
            self.P_Th_Act_var.lb = self.P_Th_Schedule[timestep]
            self.P_Th_Act_var.ub = self.P_Th_Schedule[timestep]

    def calculate_co2(self, schedule=None, timestep=None, co2_emissions=None):
        """Calculate CO2 emissions of the Boiler.

        Parameters
        ----------
        schedule : str, optional
            Specify which schedule to use.
            `None` : Normal schedule
            'act', 'actual' : Actual schedule
            'ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        p = util.get_schedule(self, schedule, timestep, thermal=True)
        co2 = -(sum(p) * self.time_slot / self.eta
                * constants.CO2_EMISSIONS_GAS)
        return co2
