import numpy as np
import gurobi
import pycity_base.classes.supply.HeatPump as hp

from .thermal_entity import ThermalEntity
from .electrical_entity import ElectricalEntity


class HeatPump(ThermalEntity, ElectricalEntity, hp.Heatpump):
    """
    Extension of pycity class Heatpump for scheduling purposes.
    """

    def __init__(self, environment, P_Th_Nom, hp_type="aw", tAmbient=None,
                 tFlow=45, cop=None, tMax=55, lowerActivationLimit=0,
                 heat=None, power=None):
        """Initialize HeatPump.

        Parameters
        ----------
        environment : pycity_scheduling.classes.Environment
            Common to all other objects. Includes time and weather instances.
        P_Th_Nom : float
            Nominal thermal power of the heatpump in [kW].
        hp_type : {"aw", "ww"}
            Type of heatpump (air-water or water-water).
        tAmbient : array_like, optional
            Source temperatures in [°K].
        tFlow : float, optional
            Flow temperature in [°C].
        cop : array_like, optional
            Coefficient of performance for different ambient and flow
            temperatures
        tMax :

        lowerActivationLimit:
            Minimal percentage the heatpump operates with. If this value is
            larger than zero, the heatpump never turns fully off.
        heat
        power
        """
        simu_horizon = environment.timer.simu_horizon
        if tAmbient is None:
            if hp_type == "aw":
                (tAmbient,) = environment.weather.getWeatherForecast(
                    getTAmbient=True
                )
                ts = environment.timer.time_in_year()
                tAmbient = tAmbient[ts:ts+simu_horizon]
            else:
                tAmbient = np.full(simu_horizon, 283)
        if cop is None:
            relative_COP = (0.36 if hp_type == "aw" else 0.5)
            cop = [relative_COP * (tFlow + 273) / (tFlow - tAmbient[t])
                   for t in range(simu_horizon)]  # TODO: better implementation
        super(HeatPump, self).__init__(environment.timer, environment,
                                       tAmbient, tFlow, heat, power, cop, tMax,
                                       lowerActivationLimit)
        self._long_ID = "HP_" + self._ID_string
        self.COP = cop
        self.P_Th_Nom = P_Th_Nom

        self.El_Th_Coupling_constr = None

    def populate_model(self, model, mode=""):
        """Add variables to Gurobi model.

        Call parent's `populate_model` method and set thermal variables lower
        bounds to `-self.P_Th_Nom` and the upper bounds to zero. Also add
        constraint to bind electrical demand to thermal output.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        ThermalEntity.populate_model(self, model, mode)
        ElectricalEntity.populate_model(self, model, mode)

        for var in self.P_Th_vars:
            var.lb = -self.P_Th_Nom
            var.ub = -self.lowerActivationLimit*self.P_Th_Nom

        for t in self.op_time_vec:
            model.addConstr(
                -self.P_Th_vars[t] == self.COP[t] * self.P_El_vars[t],
                "{0:s}_Th_El_coupl_at_t={1}".format(self._long_ID, t)
            )

    def update_schedule(self, mode=""):
        ThermalEntity.update_schedule(self, mode)
        ElectricalEntity.update_schedule(self, mode)

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the heatpump wheighted with coeff.
        Sum of self.P_El_vars.

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
