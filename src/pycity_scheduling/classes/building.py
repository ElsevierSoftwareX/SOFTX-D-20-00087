"""
The pycity_scheduling framework


Copyright (C) 2022,
Institute for Automation of Complex Power Systems (ACS),
E.ON Energy Research Center (E.ON ERC),
RWTH Aachen University

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.building as bd

from pycity_scheduling import classes
from pycity_scheduling.classes.entity_container import EntityContainer


class Building(EntityContainer, bd.Building):
    """
    Extension of pyCity_base class Building for scheduling purposes.

    Parameters
    ----------
    environment : Environment
        Common to all other objects. Includes time and weather instances.
    objective : str, optional
        Objective for the scheduling. The default is 'price'.

        - 'price' : Optimize for the prices given by `prices.tou_prices`.
        - 'co2' : Optimize for the CO2 emissions given by `prices.co2_prices`.
        - 'peak-shaving' : Try to flatten the schedule as much as possible.
        - 'max-consumption' : Try to reduce the maximum of the absolute values of the schedule as much as possible.
        - 'self-consumption' : Try to maximize the self-consumption of the local power generation.
        - 'none' : No objective (leave all flexibility to other participants).
    name : str, optional
        Name for the building.
        If name is None, set it to self._long_id.
    profile_type : str, optional
        Thermal SLP profile name
        Requires `method=1`

        - 'HEF' : Single family household
        - 'HMF' : Multi family household
        - 'GBA' : Bakeries
        - 'GBD' : Other services
        - 'GBH' : Accommodations
        - 'GGA' : Restaurants
        - 'GGB' : Gardening
        - 'GHA' : Retailers
        - 'GHD' : Summed load profile business, trade and services
        - 'GKO' : Banks, insurances, public institutions
        - 'GMF' : Household similar businesses
        - 'GMK' : Automotive
        - 'GPD' : Paper and printing
        - 'GWA' : Laundries
    building_type : str, optional
        Build year profile name, the detailed list is implemented in
        `tabula_data.py`.
    storage_end_equality : bool, optional
        `True` if the soc at the end of the scheduling has to be equal to
        the initial soc.
        `False` if it has to be greater or equal than the initial soc.

    Notes
    -----
    - The exchange of thermal energy between different buildings is currently not supported.
      As a result, the building adds the following set of constrains additionally to the
      ones of the EntityContainer:

    .. math::
        p_{th\\_heat} &=& 0 \\\\
        p_{th\\_cool} &=& 0

    - The building can also add robustness constrains for thermal heating storage:

    .. math::
        e_{u\\_bound} \\geq \\sum_i e_{th\\_heat\\_i} \\geq e_{l\\_bound} \\\\

    - The :math:`E_{u\\_bound}` and :math:`E_{l\\_bound}` are determined by the
      robustness parameter, the available capacity of thermal heating storage, the magnitude of heating
      required by SpaceHeating and the magnitude of heating that can be produced by the building's heating units.
    """

    def __init__(self, environment, objective='price', name=None,
                 profile_type=None, building_type=None,
                 storage_end_equality=False):
        super().__init__(environment)

        self._long_id = "BD_" + self._id_string
        if name is None:
            self.name = self._long_id
        else:
            self.name = name

        self.objective = objective
        self.profile_type = profile_type
        self.building_type = building_type
        self.storage_end_equality = storage_end_equality

    def populate_model(self, model, mode="convex", robustness=None):
        """
        Add building block to pyomo ConcreteModel.

        Call parent's `populate_model` method and set variables lower
        bounds to `None`. Then call `populate_model` method of the BES
        and all contained apartments and add constraints that the sum
        of their variables for each period equals the corresponding
        own variable.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        """
        if not self.has_bes:
            raise AttributeError(
                "No BES object in %s, but a BES is always required.\nModeling aborted." % str(self)
            )
        super().populate_model(model, mode)
        m = self.model

        def p_th_cool_equality_rule(model, t):
            return model.p_th_cool_vars[t] == 0
        m.p_th_cool_equality_constr = pyomo.Constraint(m.t, rule=p_th_cool_equality_rule)

        def p_th_heat_equality_rule(model, t):
            return model.p_th_heat_vars[t] == 0
        m.p_th_heat_equality_constr = pyomo.Constraint(m.t, rule=p_th_heat_equality_rule)

        if robustness is not None and (self.bes.getHasDevices(all_devices=False, ths=True)[0]):
            self._create_robust_constraints()
        return

    def update_model(self, mode="", robustness=None):
        """
        Update block parameters and bounds.

        Set parameters and bounds according to the current situation of the device
        according to the previous schedule and the current forecasts.

        Parameters
        ----------
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        robustness : tuple, optional
            Tuple of two floats. First entry defines how many time steps are
            protected from deviations. Second entry defines the magnitude of
            deviations which are considered.
        """
        super().update_model(mode)

        if robustness is not None and (self.bes.getHasDevices(all_devices=False, ths=True)[0]):
            self._update_robust_constraints(robustness)
        return

    def _create_robust_constraints(self):
        # ToDo: Robust constraints currently available for heating devices only. Also include them for cooling devices.

        m = self.model
        ths_ms = [ths.model for ths in self.bes.ths_units]
        m.lower_robustness_bounds = pyomo.Param(m.t, mutable=True)
        m.upper_robustness_bounds = pyomo.Param(m.t, mutable=True)

        def e_lower_rule(model, t):
            return sum(ths.e_th_heat_vars[t] for ths in ths_ms) >= model.lower_robustness_bounds[t]
        m.lower_robustness_constr = pyomo.Constraint(m.t, rule=e_lower_rule)

        def e_upper_rule(model, t):
            return sum(ths.e_th_heat_vars[t] for ths in ths_ms) <= model.upper_robustness_bounds[t]
        m.upper_robustness_constr = pyomo.Constraint(m.t, rule=e_upper_rule)
        return

    def _update_robust_constraints(self, robustness):
        # ToDo: Robust constraints currently available for heating devices only. Also include them for cooling devices.

        m = self.model
        timestep = self.timer.current_timestep
        e_th_max = sum(ths.e_th_max for ths in self.bes.ths_units)
        end_value = sum(ths.soc_init * ths.e_th_max for ths in self.bes.ths_units)
        uncertain_p_th = np.zeros(self.op_horizon)
        p_th_demand_sum = np.zeros(self.op_horizon)

        # aggregate demand from all thermal heating demands
        t1 = timestep
        t2 = timestep + self.op_horizon
        for apartment in self.apartments:
            for entity in apartment.th_heating_demand_list:
                if isinstance(entity, classes.SpaceHeating):
                    p_th_demand_sum += entity.p_th_heat_schedule[t1:t2]

        p_th_max_supply = sum(
            e.p_th_nom for e in classes.filter_entities(self, 'heating_devices')
        )

        # Get parameter for robustness conservativeness
        lambda_i, lambda_d = divmod(robustness[0], 1)
        lambda_i = int(lambda_i)
        if lambda_i >= self.op_horizon:
            lambda_i = self.op_horizon - 1
            lambda_d = 1

        for t in self.op_time_vec:
            uncertain_p_th[t] = min(p_th_demand_sum[t] * robustness[1],
                                    p_th_max_supply)
            tmp = sorted(uncertain_p_th, reverse=True)
            uncertain_e_th = self.time_slot * (sum(tmp[:lambda_i])
                                               + tmp[lambda_i]*lambda_d)

            # If environment is too uncertain, keep storage on half load
            if uncertain_e_th >= e_th_max / 2:
                m.lower_robustness_bounds[t] = e_th_max / 2
                m.upper_robustness_bounds[t] = e_th_max / 2
            # standard case in
            elif t < self.op_horizon - 1:
                m.upper_robustness_bounds[t] = e_th_max - uncertain_e_th
                m.lower_robustness_bounds[t] = uncertain_e_th
            # set storage to uncertain_e_th or set SOC_End to soc_init to
            # prevent depletion of storage
            else:
                if e_th_max / end_value <= 0.5:
                    end_value = max(end_value, uncertain_e_th)
                else:
                    end_value = min(end_value, e_th_max - uncertain_e_th)
                m.lower_robustness_bounds[t] = end_value
                m.upper_robustness_bounds[t] = end_value
        return

    def get_lower_entities(self):
        if self.has_bes:
            yield self.bes
        yield from self.apartments
