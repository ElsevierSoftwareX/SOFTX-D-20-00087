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

from pycity_scheduling.util import extract_pyomo_values


class OptimizationEntity(object):
    """
    Base class for all optimization entities.

    This class provides functionality common to all entities which take part
    in the scheduling optimization.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    """

    static_entity_id = 0

    def __init__(self, environment, *args, **kwargs):
        OptimizationEntity.static_entity_id += 1
        self.id = OptimizationEntity.static_entity_id
        self._id_string = "{0:05d}".format(self.id)
        self._long_id = ""
        self._kind = ""

        self.objective = None
        self.timer = environment.timer
        self.schedules = {'default': {}, 'ref': {}}

        self._var_order = []
        self._var_funcs = {}
        self.current_schedule_active = 'default'
        self.model = None

        if hasattr(super(), "__module__"):
            # This allows ElectricalEntity and ThermalEntity to be instantiated on their own:
            super().__init__(environment, *args, **kwargs)
        else:
            super().__init__()

    def __str__(self):
        return self._long_id

    def __repr__(self):
        return ("<OptimizationEntity of kind " + self._kind
                + " with ID: " + self._long_id + ">")

    @property
    def op_horizon(self):
        """
        Number of time steps in a scheduling period.
        """
        return self.timer.timesteps_used_horizon

    @property
    def op_time_vec(self):
        """
        Iterator over scheduling period.
        """
        return range(self.timer.timesteps_used_horizon)

    @property
    def simu_horizon(self):
        """
        Number of time steps in the whole simulation horizon.
        """
        return self.timer.simu_horizon

    @property
    def time_slot(self):
        """
        Length of a time step as a portion of an hour.

        Examples
        --------
        time step length = 60 mins => time_slot = 1
        time step length = 15 mins => time_slot = 0.25
        """
        return self.timer.time_slot

    @property
    def timestep(self):
        """
        Time step indicating the current scheduling.
        """
        return self.timer.current_timestep

    @property
    def op_slice(self):
        """
        Slice to select values of current scheduling from whole horizon.
        """
        t1 = self.timer.current_timestep
        t2 = t1 + self.timer.timesteps_used_horizon
        return slice(t1, t2)

    def populate_model(self, model, mode=""):
        """
        Add entity block to pyomo ConcreteModel.

        Places the block with the name of the entity in the ConcreteModel.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : May use integer variables
        """
        # generate empty pyomo block
        self.model = pyomo.Block()
        setattr(model, "_".join([self._kind, self._id_string]), self.model)
        # add time
        self.model.t = pyomo.RangeSet(0, self.op_horizon-1)
        return

    def update_model(self, mode=""):
        """
        Update block parameters and bounds.

        Set parameters and bounds according to the current situation of the
        device according to the previous schedule and the current forecasts.

        Parameters
        ----------
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Use integer variables representing discrete control decisions
        """
        pass

    def update_schedule(self):
        """
        Update the schedule with the scheduling model solution.

        Retrieve the solution from the scheduling model and write it to the
        schedule. The model must be optimal. The time / position of the
        solution in the schedule is determined by `self.timer.current_timestep`.
        """
        op_slice = self.op_slice
        for name in self._var_order:
            schedule = self.schedule[name]
            if name in self._var_funcs and not hasattr(self.model, name + "_vars"):
                func = self._var_funcs[name]
                schedule[op_slice] = func(self.model)
            else:
                values = extract_pyomo_values(getattr(self.model, name + "_vars"))
                if len(values) < self.op_horizon:
                    values = np.pad(values, (0, len(schedule[op_slice]) - len(values)), mode='constant')
                schedule[op_slice] = values
        return

    def set_objective(self, objective):
        """
        Set a new objective to be returned by get_objective.

        Parameters
        ----------
        objective : str
            Objective for the scheduling.

            - 'none' : No objective (leave all flexibility to other participants).
        """
        self.objective = objective
        return

    def get_objective(self, coeff=1):
        """
        Objective function for entity level scheduling.

        Return the objective function of the entity weighted with
        coeff.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.

        Returns
        -------
        ExpressionBase :
            Objective function.
        """
        if self.objective is None or self.objective == 'none':
            return 0
        else:
            raise ValueError(
                "Objective {} is not implemented by entity {}.".format(self.objective, self.__class__.__name__)
            )

    def reset(self, schedule=None):
        """
        Reset all values of specified schedule.

        Parameters
        ----------
        schedule : str, optional
            Specify which schedule to reset.

            - `None` : Resets all schedules
            - 'default' : Resets normal schedule
            - 'ref' : Resets reference schedule
        """
        if schedule is None:
            for name in self.schedules.keys():
                self.new_schedule(name)
        else:
            self.new_schedule(schedule)
        return

    def get_entities(self):
        """
        Yield all lowest contained entities.

        Yields
        ------
        Lowest contained entities or `self`.
        """
        top = False
        for entity in self.get_lower_entities():
            top = True
            yield from entity.get_entities()
        if not top:
            yield self

    def get_lower_entities(self):
        """
        Yield all lower-level entities.

        Yields
        ------
        All contained entities.
        """
        return iter(())

    def get_all_entities(self):
        """
        Yield all entities.

        Yields
        ------
        All contained entities and sub-entities.
        """
        yield self
        for entity in self.get_lower_entities():
            yield from entity.get_all_entities()

    def new_var(self, name, dtype=np.float64, func=None):
        """
        Create a new entry and empty schedule for variable with specified name.

        Parameters
        ----------
        name : str
            Name to access new variable with.
        dtype : numpy.dtype, optional
            Data type which should be used for new schedule.
        func : Callable[[int], Any], optional
            Function to generate schedule with.
            If `None`, schedule is generated with values of variables.
        """
        if func is not None:
            self._var_funcs[name] = func
        for schedule in self.schedules.values():
            schedule[name] = np.full(self.timer.simu_horizon, 0, dtype=dtype)
            self._var_order.append(name)
        return

    def new_schedule(self, schedule):
        """
        Create a new schedule with default values.

        Parameters
        ----------
        schedule : str
            Name of new schedule.
        """
        self.schedules[schedule] = {name: np.full_like(entries, 0) for name, entries in self.schedule.items()}
        for e in self.get_lower_entities():
            e.new_schedule(schedule)
        return

    def copy_schedule(self, dst=None, src=None, name=None):
        """
        Copy values of one schedule in another schedule.

        Parameters
        ----------
        dst : str
            Name of schedule to insert values into.
            If `None`, use current schedule.
        src : str
            Name of schedule to copy values from.
            If `None`, use current schedule.
        name : str
            Name of variable to copy sub schedule of.
            If `None`, copy all variables between schedules.
        """
        assert dst != src
        if dst is None:
            dst = self.current_schedule_active
        elif src is None:
            src = self.current_schedule_active
        src_schedule = self.schedules[src]
        if name is None:
            self.schedules[dst] = {key: entries.copy() for key, entries in src_schedule.items()}
        else:
            if dst not in self.schedules:
                self.new_schedule(dst)
            self.schedules[dst][name] = src_schedule[name].copy()
        for e in self.get_lower_entities():
            e.copy_schedule(dst, src, name)
        return

    def load_schedule(self, schedule):
        """
        Copy values of one schedule in another schedule.

        Parameters
        ----------
        schedule : str
        Name of schedule to set as current schedule.
        """
        self.current_schedule_active = schedule
        for e in self.get_lower_entities():
            e.load_schedule(schedule)
        return

    def load_schedule_into_model(self, schedule=None):
        """
        Overwrites the values in the entity model with the values in the schedule.

        Parameters
        ----------
        schedule : str
            Name of schedule to load values from.
            If `None`, use current schedule.
        """
        if schedule is None:
            s = self.schedule
        else:
            s = self.schedules[schedule]
        op_slice = self.op_slice
        for var_name, var_schedule in s.items():
            var_schedule = var_schedule[op_slice]
            if not hasattr(self.model, var_name + "_vars"):
                continue
            vars = getattr(self.model, var_name + "_vars")
            for t in range(self.op_horizon):
                if t in vars:
                    vars[t].value = var_schedule[t]

        for e in self.get_lower_entities():
            e.load_schedule_into_model(schedule)
        return

    @property
    def schedule(self):
        """
        The current loaded schedule.
        """
        return self.schedules[self.current_schedule_active]

    def __getattr__(self, item):
        if isinstance(item, str):
            items = item.split("_")
            if len(items) >= 2:
                if items[-1] == "schedule":
                    if items[-2] in self.schedules and "_".join(items[:-2]) in self.schedule:
                        schedule = self.schedules[items[-2]]
                        varname = "_".join(items[:-2])
                    else:
                        schedule = self.schedule
                        varname = "_".join(items[:-1])
                    schedule = schedule.get(varname, None)
                    if schedule is not None:
                        return schedule
        raise AttributeError(item)

    def __setattr__(self, attr, value):
        if isinstance(attr, str):
            attrs = attr.split("_")
            if len(attrs) >= 2:
                if attrs[-1] == "schedule":
                    if attrs[-2] in self.schedules and "_".join(attrs[:-2]) in self.schedule:
                        schedule = self.schedules[attrs[-2]]
                        varname = "_".join(attrs[:-2])
                    else:
                        schedule = self.schedule
                        varname = "_".join(attrs[:-1])
                    schedule[varname] = value
                    return
        super().__setattr__(attr, value)
