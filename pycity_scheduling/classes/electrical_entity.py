import numpy as np
import gurobipy as gurobi

from pycity_scheduling import constants, classes, util
from .optimization_entity import OptimizationEntity


class ElectricalEntity(OptimizationEntity):
    """
    Base class for all electrical entities derived from OptimizationEntity.

    This class provides functionality common to all electrical entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("P_El")

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model.

        Add variables for the electrical demand / supply of the entity to the
        optimization model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        if mode in ["convex", "integer"]:
            for t in self.op_time_vec:
                self.P_El_vars.append(
                    model.addVar(
                        name="%s_P_El_at_t=%i" % (self._long_ID, t+1)
                    )
                )
            model.update()
        else:
            raise ValueError(
                "Mode %s is not implemented by electric entity." % str(mode)
                )

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

        Return the objective function of the EE wheighted with coeff.
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

    def calculate_costs(self, timestep=None, prices=None,
                        feedin_factor=None):
        """Calculate electricity costs for the ElectricalEntity with the current schedule.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
        feedin_factor : float, optional
            Factor which is multiplied to the prices for feed-in revenue.

        Returns
        -------
        float :
            Electricity costs in [ct].
        """
        p = self.P_El_Schedule
        if prices is None:
            prices = self.environment.prices.tou_prices
        if timestep:
            prices = prices[:timestep]
            p = p[:timestep]
        if feedin_factor is None:
            feedin_factor = self.environment.prices.feedin_factor
        costs = self.time_slot * np.dot(prices[p>0], p[p>0])
        costs += self.time_slot * np.dot(prices[p<0], p[p<0]) * feedin_factor
        return costs

    def calculate_adj_costs(self, schedule, timestep=None, prices=None,
                            total_adjustments=True):
        """Calculate costs for adjustments.

        Parameters
        ----------
        schedule : str, optional
           Schedule to adjust to.
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Adjustment prices for all timesteps in simulation horizon.
        total_adjustments : bool, optional
            `True` if positive and negative deviations shall be considered.
            `False` if only positive deviations shall be considered.

        Returns
        -------
        float :
            Adjustment costs in [ct].
        """
        if prices is None:
            prices = self.environment.prices.tou_prices
        if timestep:
            prices = prices[:timestep]
        adj_power = self.calculate_adj_power(schedule, timestep, total_adjustments)
        costs = self.time_slot * np.dot(adj_power, prices)
        return costs


    def calculate_co2(self, timestep=None, co2_emissions=None):
        """Calculate CO2 emissions of the entity with the current schedule.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate emissions only to this timestep.
        co2_emissions : array_like, optional
            Specific CO2 emissions for all timesteps in the simulation horizon
            in [g/kWh].

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        if timestep is None:
            timestep = len(self.P_El_Schedule)
        p = self.P_El_Schedule[:timestep]
        if co2_emissions is None:
            co2_emissions = self.environment.prices.co2_prices
        co2_emissions = co2_emissions[:timestep]
        bat_schedule = sum(
            e.P_El_Schedule[:timestep]
            for e in classes.filter_entities(self, 'BAT')
        )
        # TODO this ignores battery losses right now
        p = p - bat_schedule
        co2 = self.time_slot * np.dot(p[p>0], co2_emissions[p>0])

        gas_schedule = sum(
            e.P_Th_Schedule[:timestep].sum()
            * (1+e.sigma) / e.omega
            for e in classes.filter_entities(self, 'CHP')
        )
        gas_schedule += sum(
            e.P_Th_Schedule[:timestep].sum()
            / e.eta
            for e in classes.filter_entities(self, 'BL')
        )
        pv_schedule = sum(
            e.P_El_Schedule[:timestep].sum()
            for e in classes.filter_entities(self, 'PV')
        )
        wec_schedule = sum(
            e.P_El_Schedule[:timestep].sum()
            for e in classes.filter_entities(self, 'WEC')
        )
        co2 -= gas_schedule * self.time_slot * constants.CO2_EMISSIONS_GAS
        co2 -= pv_schedule * self.time_slot * constants.CO2_EMISSIONS_PV
        co2 -= wec_schedule * self.time_slot * constants.CO2_EMISSIONS_WIND

        return co2

    def calculate_adj_power(self, schedule, timestep=None, total_adjustments=True):
        """Compute adjustment power.

        Parameters
        ----------
        schedule : str, optional
           Schedule to adjust to.
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate power curve up to this timestep only.
        total_adjustments : bool, optional
            `True` if positive and negative deviations shall be considered.
            `False` if only positive deviations shall be considered.

        Returns
        -------
        array of float :
            Adjustment power in [kW].
        """
        adjustments = self.schedules[schedule]["P_El"] - self.P_El_Schedule
        if timestep:
            adjustments = adjustments[:timestep]
        if total_adjustments:
            return abs(adjustments)
        else:
            return np.maximum(adjustments, 0)

    def calculate_adj_energy(self, schedule, timestep=None, total_adjustments=True):
        """Compute the cumulated absolute energy of all adjustments.

        Parameters
        ----------
        schedule : str, optional
           Schedule to adjust to.
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate energy only to this timestep.
        total_adjustments : bool, optional
            `True` if positive and negative deviations shall be considered.
            `False` if only positive deviations shall be considered.

        Returns
        -------
        float :
            Adjustments in [kWh].
        """
        p = self.calculate_adj_power(schedule, timestep, total_adjustments)
        adjustments = self.time_slot * sum(p)
        return adjustments

    def metric_delta_g(self, schedule):
        """Compute the factor "Delta g" with the current schedule and the referenced schedule.

        Compute the factor :math:`\Delta` g based on the optimized schedules,
        assuming that `city_district` holds the schedule of a DSM optimization.

        Returns
        -------
        schedule : str
           Referenced Schedule
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
        float :
            Factor "Delta g".

        Notes
        -----
         - Implementation as given in the lecture "Elektrizitaetswirtschaft"
           by Prof. Dr.-Ing. Christian Rehtanz at TU Dortmund.
        """
        P_El_Min_dsm = min(self.P_El_Schedule)
        P_El_Max_dsm = max(self.P_El_Schedule)
        P_El_Min_ref = min(self.schedules[schedule]["P_El"])
        P_El_Max_ref = max(self.schedules[schedule]["P_El"])
        g = 1 - (abs(P_El_Max_dsm - P_El_Min_dsm)
                 / abs(P_El_Max_ref - P_El_Min_ref))
        return g

    def peak_to_average_ratio(self, timestep=None):
        """Compute the ratio of peak demand to average demand.

        The ratio of the absolute peak demand of the specified schedule
        compared to the absolute mean of the schedule.
        `r` >= 1; a lower value is better, 1 would be optimal (no peaks at
        all).

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate ratio only to this timestep.

        Returns
        -------
        float :
            Peak to average ratio.
        """
        p = self.P_El_Schedule
        if timestep is not None:
            p = p[:timestep]
        peak = max(max(p), -min(p))
        mean = abs(np.mean(p))
        r = peak / mean
        return r

#TODO if 'r' > 0??
    def peak_reduction_ratio(self, schedule, timestep=None):
        """Compute the ratio of the peak reduction.

        The reduction of the absolute peak demand of the current schedule
        compared to the peak demand in the referenced schedule.
        If `r` < 1 the specified schedule has lower peaks, otherwise the
        referenced schedule has lower peaks. Normally a lower value is better.

        Parameters
        ----------
        schedule : str
            Name of Schedule to compare to
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
        timestep : int, optional
            If specified, calculate ratio only to this timestep.

        Returns
        -------
        float :
            Peak reduction ratio.
        """
        if timestep is None:
            timestep = len(self.P_El_Schedule)
        p = self.P_El_Schedule[:timestep]
        ref = self.schedules[schedule]["P_El"][:timestep]
        dr_peak = max(max(p), -min(p))
        ref_peak = max(max(ref), -min(ref))
        r = (dr_peak - ref_peak) / ref_peak
        return r

    def self_consumption(self, timestep=None):
        """Calculate the self consumption of the current schedule.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate self consumption only to this timestep.

        Returns
        -------
        float :
            Self consumption.
        """
        if timestep is None:
            timestep = len(self.P_El_Schedule)
        p = self.P_El_Schedule[:timestep]
        res_schedule = sum(e.P_El_Schedule[:timestep] for e in classes.filter_entities(self, 'res_devices'))

        if not isinstance(res_schedule, np.ndarray):
            return 0
        generation = sum(res_schedule)
        if generation == 0:
            return 1
        neg_load = res_schedule - p
        np.clip(neg_load, a_min=None, a_max=0, out=neg_load)
        consumption = sum(np.maximum(neg_load, res_schedule))
        self_consumption = consumption / generation
        return self_consumption

    def autarky(self, timestep=None):
        """Calculate the autarky of the current schedule.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate autarky only to this timestep.

        Returns
        -------
        float :
            Autarky.
        """
        if timestep is None:
            timestep = len(self.P_El_Schedule)
        p = self.P_El_Schedule[:timestep]
        res_schedule = - sum(e.P_El_Schedule[:timestep] for e in classes.filter_entities(self, 'res_devices'))
        if not isinstance(res_schedule, np.ndarray):
            return 0

        load = p + res_schedule
        np.clip(load, a_min=0, a_max=None, out=load)
        consumption = sum(load)
        if consumption == 0:
            return 1
        cover = sum(np.minimum(res_schedule, load))
        autarky = cover / consumption
        return autarky
