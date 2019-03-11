import gurobipy as gurobi
import pycity_base.classes.demand.ElectricalDemand as ed

from .electrical_entity import ElectricalEntity


class CurtailableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
    """

    def __init__(self, environment, MaxCurtailment, method=0, demand=0,
                 annualDemand=0, profileType="H0", singleFamilyHouse=True):
        """Initialize a curtailable load.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        MaxCurtailment : float
            Maximal Curtailment of the load
        method : {0, 1}, optional
            - 0: provide load curve directly
            - 1: standard load profile
        demand : array_like of float, optional
            Loadcurve for all investigated time steps in [kW].
        annualDemand : float
            Required for SLP and recommended for method 2.
            Annual electrical demand in [kWh].
            If method 2 is chosen but no value is given, a standard value for
            Germany (http://www.die-stromsparinitiative.de/fileadmin/bilder/
            Stromspiegel/Brosch%C3%BCre/Stromspiegel2014web_final.pdf) is used.
        profileType : String (required for SLP)
            - H0 : Household
            - L0 : Farms
            - L1 : Farms with breeding / cattle
            - L2 : Farms without cattle
            - G0 : Business (general)
            - G1 : Business (workingdays 8:00 AM - 6:00 PM)
            - G2 : Business with high loads in the evening
            - G3 : Business (24 hours)
            - G4 : Shops / Barbers
            - G5 : Bakery
            - G6 : Weekend operation
        """
        super(CurtailableLoad, self).__init__(
            environment.timer, environment, method, demand * 1000,
            annualDemand, profileType, singleFamilyHouse
        )
        self._long_ID = "CUL_" + self._ID_string

        self.max_curt = MaxCurtailment

        if method == 0:
            self.P_El_Demand = demand
        else:
            self.P_El_Demand = self.loadcurve / 1000

        self.P_El_Curt_Demand = self.P_El_Demand * self.max_curt

    def populate_model(self, model, mode=""):
        """Add variables to Gurobi model

        Call parent's `populate_model` method and set variables upper bounds to
        the loadcurve and lower bounds to s`elf.P_El_Min`.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        super(CurtailableLoad, self).populate_model(model, mode)
        time_shift = self.timer.currentTimestep
        for t in self.op_time_vec:
            self.P_El_vars[t].lb = self.P_El_Curt_Demand[t+time_shift]
            self.P_El_vars[t].ub = self.P_El_Demand[t+time_shift]

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the curtailable load wheighted with
        coeff. Quadratic term minimizing the deviation from the loadcurve.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        obj = gurobi.QuadExpr()
        obj.addTerms(
            [coeff] * self.op_horizon,
            self.P_El_vars,
            self.P_El_vars
        )
        obj.addTerms(
            [- 2 * coeff] * self.op_horizon,
            self.P_El_vars
        )
