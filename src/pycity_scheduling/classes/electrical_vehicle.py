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
from warnings import warn

from pycity_scheduling.classes.battery import Battery
from pycity_scheduling import util


class ElectricalVehicle(Battery):
    """
    Class representing an electrical vehicle for scheduling purposes.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    e_el_max : float
        Electric capacity of the battery in [kWh].
    p_el_max_charge : float
        Maximum charging power in [kW].
    p_el_max_discharge : float, optional
        Maximum discharging power in [kW]. Defaults to zero.
    soc_init : float, optional
        Initial state of charge. Defaults to 50%.
    charging_time : array of binaries, optional
        Indicator when electrical vehicle can be charged.

        - `charging_time[t] == 0`: EV cannot be charged in t
        - `charging_time[t] == 1`: EV can be charged in t

        It must contain at least one `0` otherwise the model will become
        infeasible. Its length has to be consistent with `ct_pattern`.
        Defaults to only charge during night.
    ct_pattern : str, optional
        Define how the `charging_time` profile is to be used.

        - `None` : Profile matches simulation horizon (default).
        - 'daily' : Profile matches one day.
        - 'weekly' : Profile matches one week.

    Notes
    -----
    - EVs offer sets of constraints for operation. The :math:`e_{el}` equivalence
      constraint is replaced by the following constraint:

    .. math::
        e_{el} &=& e_{el\\_previous} + (\\eta * p_{el\\_demand}
        - (1 / \\eta) * p_{el\\_supply} - p_{el\\_drive}) * \\Delta t \\\\

    - The following constraints are added:

    .. math::
        p_{el\\_drive} \\geq 0 \\\\
        p_{el\\_demand\\_i} = p_{el\\_supply} = 0,
        & \\quad \\text{if} \\quad ct\\_pattern_i = 0 \\\\
        p_{el\\_drive\\_i} = 0, & \\quad \\text{if} \\quad ct\\_pattern_i = 1 \\\\
        e_{el\\_i} = soc\\_init * e_{el\\_max}, & \\quad \\text{if} \\quad \\sum_{j=0}^i ct\\_pattern_j = 0 \\\\
        e_{el\\_i} = 0.2 * e_{el\\_max}, & \\quad \\text{else if} \\quad ct\\_pattern_i = 0 \\\\
        e_{el\\_i} = e_{el\\_max}, & \\quad \\text{else if} \\quad ct\\_pattern_i+1 = 0

    - The constraint for the parameter `storage_end_equality` is removed. Instead,
      the EV needs to be fully charged at the end of the `simu_horizon` if parameter `ct_pattern`
      is one at the end of the simulation horizon.
    """

    def __init__(self, environment, e_el_max, p_el_max_charge, p_el_max_discharge=0.0,
                 soc_init=0.5, charging_time=None, ct_pattern=None):
        super().__init__(environment, e_el_max, p_el_max_charge, p_el_max_discharge, soc_init, eta=1,
                         storage_end_equality=False)
        self._kind = "electricalvehicle"
        self._long_id = "EV_" + self._id_string

        self.charging_time_initial = charging_time
        self.ct_pattern = ct_pattern

        if charging_time is None:
            # load at night, drive during day
            ts_per_day = int(24 / self.time_slot)
            a = int(ts_per_day / 4)
            b = int(ts_per_day / 2)
            c = ts_per_day - a - b
            charging_time = [1] * a + [0] * b + [1] * c
            self.ct_pattern = 'daily'
        self.charging_time = util.compute_profile(self.timer, charging_time, self.ct_pattern)

        # Contains all starting timesteps of charging periods.
        self.starting_timesteps = np.where(np.diff(charging_time, prepend=0, append=0) == 1)[0]
        # Contains all stopping timesteps of charging periods.
        self.stopping_timesteps = np.where(np.diff(charging_time, prepend=0, append=0) == -1)[0]
        # Contains all length of charging periods in timesteps.
        self.charging_durations = self.stopping_timesteps - self.starting_timesteps
        # Links charging periods to indices in previous arrays.
        self.charging_indices = np.zeros_like(charging_time, dtype=np.int)
        for i, start in enumerate(self.starting_timesteps):
            self.charging_indices[start:start + self.charging_durations[i]] = np.full(self.charging_durations[i], i)

        # Contains the amount of energy to charge in charging periods.
        self.required_charges = np.full_like(self.charging_durations, 0.8 * e_el_max, dtype=np.float)

        if len(self.charging_time) > 0:
            # In first charging cycle the required charge is determined by soc_init and is not necessarily 80%.
            self.required_charges[0] = (1 - soc_init) * e_el_max

            if self.charging_time[-1]:
                # Limit charge at end of simu horizon to not become infeasible.
                self.required_charges[-1] = min(self.required_charges[-1], self.charging_durations[-1] *
                                                self.time_slot * p_el_max_charge * self.eta_charge)

        if any(self.required_charges > self.charging_durations * self.time_slot * p_el_max_charge * self.eta_charge):
            warn("Charging pattern results in infeasible constraints.")

        self.new_var("p_el_drive")

    def populate_model(self, model, mode="convex"):
        """
        Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method. Replace coupling
        constraints from Battery class with coupling constraints
        of EV. Simulate power consumption while driving.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        super().populate_model(model, mode)
        m = self.model

        if mode == "convex" or "integer":
            # Simulate power consumption while driving
            m.p_el_drive_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)

            # Replace coupling constraints from Battery class
            m.del_component("e_constr")
            m.del_component("e_end_constr")

            def e_rule(model, t):
                delta = (
                    (self.eta_charge * model.p_el_demand_vars[t]
                     - (1.0 / self.eta_discharge) * model.p_el_supply_vars[t]
                     - model.p_el_drive_vars[t])
                    * self.time_slot
                )
                e_el_last = model.e_el_vars[t - 1] if t >= 1 else model.e_el_init
                return model.e_el_vars[t] == e_el_last + delta
            m.e_constr = pyomo.Constraint(m.t, rule=e_rule)
        else:
            raise ValueError(
                "Mode %s is not implemented by class ElectricalVehicle." % str(mode)
            )
        return

    def update_model(self, mode=""):
        m = self.model

        super().update_model(mode)

        timestep = self.timestep
        charging_time = self.charging_time[self.op_slice]
        # Is true if t is before the initial charging period.
        is_initial = not any(self.charging_time[:timestep])

        # Reset e_el bounds
        for t in self.op_time_vec:
            m.e_el_vars[t].setub(self.e_el_max)
            m.e_el_vars[t].setlb(0.0)

        for t in self.op_time_vec:
            if charging_time[t]:
                m.p_el_demand_vars[t].setub(self.p_el_max_charge)
                m.p_el_supply_vars[t].setub(self.p_el_max_discharge)
                m.p_el_drive_vars[t].setub(0.0)
                is_initial = False
            else:
                m.p_el_demand_vars[t].setub(0.0)
                m.p_el_supply_vars[t].setub(0.0)
                m.p_el_drive_vars[t].setub(None)

                if is_initial:
                    # Remain at soc_init before the first charging period is reached.
                    m.e_el_vars[t].setub(self.soc_init * self.e_el_max)
                    m.e_el_vars[t].setlb(self.soc_init * self.e_el_max)
                else:
                    m.e_el_vars[t].setub(0.2 * self.e_el_max)
                    m.e_el_vars[t].setlb(0.2 * self.e_el_max)

            if t + 1 < self.op_horizon:
                if charging_time[t] and not charging_time[t+1]:
                    # Full battery at end of charging period
                    m.e_el_vars[t].setub(self.e_el_max)
                    m.e_el_vars[t].setlb(self.e_el_max)

        if charging_time[-1]:
            current_ts = (timestep + self.op_horizon - 1) % int(24 / self.time_slot)
            i = self.charging_indices[current_ts]

            first_ts = self.starting_timesteps[i]
            portion_charge = (current_ts - first_ts + 1) * self.required_charges[i] / self.charging_durations[i]
            starting_charge = 0.2 * self.e_el_max if i != 0 else self.soc_init * self.e_el_max
            m.e_el_vars[self.op_horizon-1].setub(starting_charge + portion_charge)
            m.e_el_vars[self.op_horizon-1].setlb(starting_charge + portion_charge)
        return

    def get_objective(self, coeff=1):
        """
        Objective function for entity level scheduling.

        Return the objective function of the electric vehicle weighted with
        coeff. Quadratic term with additional weights to reward charging the
        vehicle earlier.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        ExpressionBase :
            Objective function.
        """
        m = self.model
        c = np.array(list(map(lambda x: x+1, range(self.op_horizon))))
        c = c * (coeff * self.op_horizon / sum(c))
        return pyomo.sum_product(c, m.p_el_vars, m.p_el_vars)
