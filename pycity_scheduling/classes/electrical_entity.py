import numpy as np
import gurobipy as gurobi

from pycity_scheduling import constants, classes, util
from .optimization_entity import OptimizationEntity
from ..exception import PyCitySchedulingGurobiException


class ElectricalEntity(OptimizationEntity):
    """
    Base class for all electrical entities derived from OptimizationEntity.

    This class provides functionality common to all electrical entities.
    """

    def __init__(self, timer, *args, **kwargs):
        super(ElectricalEntity, self).__init__(timer, *args, **kwargs)

        self.P_El_vars = []
        self.P_El_Schedule = np.zeros(self.simu_horizon)
        self.P_El_Ref_Schedule = np.zeros(self.simu_horizon)

    def populate_model(self, model, mode=""):
        """Add variables to Gurobi model.

        Add variables for the electrical demand / supply of the entity to the
        optimization model.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
        """
        self.P_El_vars = []
        for t in self.op_time_vec:
            self.P_El_vars.append(
                model.addVar(
                    name="%s_P_El_at_t=%i" % (self._long_ID, t+1)
                )
            )
        model.update()

    def update_schedule(self, mode=""):
        timestep = self.timer.currentTimestep
        try:
            self.P_El_Schedule[timestep:timestep+self.op_horizon] \
                = [var.x for var in self.P_El_vars]
        except gurobi.GurobiError:
            self.P_El_Schedule[timestep:timestep+self.op_horizon].fill(0)
            raise PyCitySchedulingGurobiException(
                "{0}: Could not read from variables."
                .format(str(self))
            )

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        np.copyto(
            self.P_El_Ref_Schedule,
            self.P_El_Schedule
        )

    def reset(self, schedule=True, reference=False):
        """Reset entity for new simulation.

        Parameters
        ----------
        schedule : bool, optional
            Specify if to reset schedule.
        reference : bool, optional
            Specify if to reset reference schedule.
        """
        if schedule:
            self.P_El_Schedule.fill(0)
        if reference:
            self.P_El_Ref_Schedule.fill(0)

    def calculate_costs(self, timestep=None, prices=None, reference=False,
                        feedin_factor=None):
        """Calculate electricity costs for the ElectricalEntity.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
        reference : bool, optional
            `True` if costs for reference schedule.
        feedin_factor : float, optional
            Factor which is multiplied to the prices for feed-in revenue.

        Returns
        -------
        float :
            Electricity costs in [ct].
        """
        p = util.get_schedule(self, reference, timestep)
        if prices is None:
            prices = self.environment.prices.tou_prices
        if timestep:
            prices = prices[:timestep]
        if feedin_factor is None:
            feedin_factor = self.environment.prices.feedin_factor
        costs = self.time_slot * np.dot(prices[p>0], p[p>0])
        costs += self.time_slot * np.dot(prices[p<0], p[p<0]) * feedin_factor
        return costs

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the entity.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate emissions only to this timestep.
        co2_emissions : array_like, optional
            Specific CO2 emissions for all timesteps in the simulation horizon
            in [g/kWh].
        reference : bool, optional
            `True` if CO2 emissions for reference schedule.

        Returns
        -------
        float :
            CO2 emissions in [g].
        """
        p = util.get_schedule(self, reference, timestep)
        if co2_emissions is None:
            co2_emissions = self.environment.prices.co2_prices
        if timestep:
            co2_emissions = co2_emissions[:timestep]
        bat_schedule = sum(
            util.get_schedule(e, reference, timestep)
            for e in classes.filter_entities(self, 'BAT')
        )
        p = p - bat_schedule
        co2 = self.time_slot * np.dot(p[p>0], co2_emissions[p>0])

        gas_schedule = sum(
            util.get_schedule(e, reference, timestep, thermal=True).sum()
            * (1+e.sigma) / e.omega
            for e in classes.filter_entities(self, 'CHP')
        )
        gas_schedule += sum(
            util.get_schedule(e, reference, timestep, thermal=True).sum()
            / e.eta
            for e in classes.filter_entities(self, 'BL')
        )
        pv_schedule = sum(
            util.get_schedule(e, reference, timestep).sum()
            for e in classes.filter_entities(self, 'PV')
        )
        wec_schedule = sum(
            util.get_schedule(e, reference, timestep).sum()
            for e in classes.filter_entities(self, 'WEC')
        )
        co2 -= gas_schedule * self.time_slot * constants.CO2_EMISSIONS_GAS
        co2 -= pv_schedule * self.time_slot * constants.CO2_EMISSIONS_PV
        co2 -= wec_schedule * self.time_slot * constants.CO2_EMISSIONS_WIND

        return co2

    def metric_delta_g(self):
        """Compute the factor "Delta g".

        Compute the factor :math:`\Delta` g based on the optimized schedules,
        assuming that `city_district` holds the schedule of a DSM optimization.

        Returns
        -------
        float :
            Factor "Delta g".

        Notes
        -----
         - Implementation as given in the lecture "Elektrizitaetswirtschaft"
           by Prof. Dr.-Ing. Christian Rehtanz at TU Dortmund.
        """
        P_El_Min_dsm = min(self.P_El_Schedule)
        P_El_Max_dsm = max(self.P_El_Schedule)
        P_El_Min_ref = min(self.P_El_Ref_Schedule)
        P_El_Max_ref = max(self.P_El_Ref_Schedule)
        g = 1 - (abs(P_El_Max_dsm - P_El_Min_dsm)
                 / abs(P_El_Max_ref - P_El_Min_ref))
        return g

    def peak_to_average_ratio(self, timestep=None, reference=False):
        """Compute the ratio of peak demand to average demand.

        The ratio of the absolute peak demand of the specified schedule
        compared to the absolute mean of the schedule.
        `r` >= 1; a lower value is better, 1 would be optimal (no peaks at
        all).

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate ratio only to this timestep.
        reference : bool, optional
            `True` if ratio for reference schedule.

        Returns
        -------
        float :
            Peak to average ratio.
        """
        p = util.get_schedule(self, reference, timestep)
        peak = max(map(abs, p))
        mean = abs(np.mean(p))
        r = peak / mean
        return r

    def peak_reduction_ratio(self, timestep=None):
        """Compute the ratio of the peak reduction.

        The reduction of the absolute peak demand of the specified schedule
        compared to the peak demand in the reference schedule.
        If `r` < 1 the specified schedule has lower peaks, otherwise the
        reference schedule has lower peaks. Normaly a lower value is better.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate ratio only to this timestep.

        Returns
        -------
        float :
            Peak reduction ratio.
        """
        p = self.P_El_Schedule
        ref = self.P_El_Ref_Schedule
        if timestep:
            p = p[:timestep]
            ref = ref[:timestep]
        dr_peak = max(map(abs, p))
        ref_peak = max(map(abs, ref))
        r = (dr_peak - ref_peak) / ref_peak
        return r

    def self_consumption(self, reference=False, timestep=None):
        """Calculate the self consumption.

        Parameters
        ----------
        reference : bool, optional
            `True` if self consumption for reference schedule.
        timestep : int, optional
            If specified, calculate self consumption only to this timestep.

        Returns
        -------
        float :
            Self consumption.
        """
        p = util.get_schedule(self, reference, timestep)
        res_schedule = sum(
            util.get_schedule(e, reference, timestep)
            for e in classes.filter_entities(self, 'res_devices')
        )
        if not isinstance(res_schedule, np.ndarray):
            return 0
        generation = res_schedule.sum()
        if generation == 0:
            return 1
        neg_load = res_schedule - p
        np.clip(neg_load, a_min=None, a_max=0, out=neg_load)
        consumption = np.maximum(neg_load, res_schedule).sum()
        self_consumption = consumption / generation
        return self_consumption

    def autarky(self, reference=False, timestep=None):
        """Calculate the autarky.

        Parameters
        ----------
        reference : bool, optional
            `True` if autarky for reference schedule.
        timestep : int, optional
            If specified, calculate autarky only to this timestep.

        Returns
        -------
        float :
            Autarky.
        """
        p = util.get_schedule(self, reference, timestep)
        res_schedule = - sum(
            util.get_schedule(e, reference, timestep)
            for e in classes.filter_entities(self, 'res_devices')
        )
        if not isinstance(res_schedule, np.ndarray):
            return 0
        load = p + res_schedule
        np.clip(load, a_min=0, a_max=None, out=load)
        consumption = load.sum()
        if consumption == 0:
            return 1
        cover = np.minimum(res_schedule, load).sum()
        autarky = cover / consumption
        return autarky
