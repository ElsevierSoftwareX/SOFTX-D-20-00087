import numpy as np
import pyomo.environ as pyomo
from pyomo.core.expr.numeric_expr import ExpressionBase
from typing import Callable, Any

class OptimizationEntity(object):
    """
    Base class for all optimization entities.

    This class provides functionality common to all entities which take part
    in the scheduling optimization.
    """

    static_entity_id = 0

    def __init__(self, environment, *args, **kwargs):
        """Set up OptimizationEntity.

        Parameters
        ----------
        timer : pycity_scheduling.classes.Timer

        """
        OptimizationEntity.static_entity_id += 1
        self.ID = OptimizationEntity.static_entity_id
        self._ID_string = "{0:05d}".format(self.ID)
        self._long_ID = ""
        self._kind = ""

        self.objective = None
        self.timer = environment.timer
        self.schedules = {'default': {}, 'Ref': {}}

        self.__var_funcs__ = {}
        self.current_schedule = 'default'
        self.model = None

        if hasattr(super(), "__module__"):
            # This allows ElectricalEntity and ThermalEntity to be instantiated
            # on their own
            super().__init__(environment, *args, **kwargs)
        else:
            super().__init__()

    def __str__(self):
        return self._long_ID

    def __repr__(self):
        return ("<OptimizationEntity of kind " + self._kind
                + " with ID: " + self._long_ID + ">")

    @property
    def op_horizon(self):
        """Number of time steps in a scheduling period."""
        return self.timer.timestepsUsedHorizon

    @property
    def op_time_vec(self):
        """Iterator over scheduling period."""
        return range(self.timer.timestepsUsedHorizon)

    @property
    def simu_horizon(self):
        """Number of time steps in the whole simulation horizon."""
        return self.timer.simu_horizon

    @property
    def time_slot(self):
        """Length of a time step as a portion of an hour.

        Examples
        --------
        time step length = 60 mins => time_slot = 1
        time step length = 15 mins => time_slot = 0.25
        """
        return self.timer.time_slot

    @property
    def timestep(self):
        """Time step indicating the current scheduling."""
        return self.timer.currentTimestep

    @property
    def op_slice(self):
        """Slice to select values of current scheduling from whole horizon."""
        t1 = self.timer.currentTimestep
        t2 = t1 + self.timer.timestepsUsedHorizon
        return slice(t1, t2)

    def populate_model(self, model, mode=""):
        """Add entity block to pyomo ConcreteModel.

        Places the block with the name of the entity in the ConcreteModel.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : May use integer variables
        """
        # generate empty pyomo block
        self.model = pyomo.Block()
        setattr(model, "_".join([self._kind, self._ID_string]), self.model)
        # add time
        self.model.t = pyomo.RangeSet(0, self.op_horizon-1)

    def update_model(self, mode=""):
        """Update block parameters and bounds.

        Set parameters and bounds according to the current situation of the
        device according to the previous schedule and the current forecasts.

        Parameters
        ----------
        Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : May use integer variables
        """
        pass

    def update_schedule(self):
        """Update the schedule with the scheduling model solution.

        Retrieve the solution from the scheduling model and write it to the
        schedule. The model must be optimal. The time / position of the
        solution in the schedule is determined by `self.timer.currentTimestep`.
        """
        op_slice = self.op_slice
        for name, schedule in self.schedule.items():
            if name in self.__var_funcs__ and not hasattr(self.model, name + "_vars"):
                func = self.__var_funcs__[name]
                values = np.fromiter((func(self.model, t) for t in self.op_time_vec), dtype=schedule.dtype)
            else:
                values = np.fromiter(getattr(self.model, name + "_vars").extract_values().values(), dtype=schedule.dtype)
            if schedule.dtype == np.bool: # TODO is this still needed?
                pad = False
            else:
                pad = True
            schedule[op_slice] = np.pad(values, (0, len(schedule[op_slice]) - len(values)), mode='constant',
                                        constant_values=pad)

    def get_objective(self, coeff=1):
        """Objective function for entity level scheduling.

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
        if self.objective is None:
            return 0
        else:
            raise ValueError(
                "Objective {} is not implemented by entity {}.".format(self.objective, self.__class__.__name__)
            )

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        import warnings
        warnings.warn("save_ref_schedule() is deprecated; use copy_schedule() instead", DeprecationWarning)
        self.copy_schedule("Ref", "default")


    def reset(self, name=None):
        """Reset all values of specified schedule.

        Parameters
        ----------
        schedule : str, optional
            Specify which schedule to reset.
            `None` : Resets all schedules
            'default' : Resets normal schedule
            'Ref', 'reference' : Resets reference schedule
        """
        if name is None:
            for name in self.schedules.keys():
                self.new_schedule(name)
        else:
            self.new_schedule(name)

    def get_entities(self):
        top = False
        for entity in self.get_lower_entities():
            top = True
            yield from entity.get_entities()
        if not top:
            yield self

    def get_lower_entities(self):
        return iter(())

    def get_all_entities(self):
        yield self
        for entity in self.get_lower_entities():
            yield from entity.get_all_entities()

    def new_var(self, name, dtype=np.float64, func=None):
        """Create a new entry and empty schedule for variable with specified name.

        Parameters
        ----------
        name : str
            Name to access new variable with.
        dtype : np.dtype, optional
            Data type which should be used for new schedule.
        func : Callable[[int], Any], optional
            Function to generate schedule with.
            If `None`, schedule is generated with values of variables.
        """
        if func is not None:
            self.__var_funcs__[name] = func
        for schedule in self.schedules.values():
            schedule[name] = np.full(self.timer.simu_horizon, 0, dtype=dtype)

    def new_schedule(self, schedule):
        """Create a new schedule with default values.

        Parameters
        ----------
        schedule : str
            Name of new schedule.
        """
        self.schedules[schedule] = {name: np.full_like(entries, 0) for name, entries in self.schedule.items()}
        for e in self.get_lower_entities():
            e.new_schedule(schedule)

    def copy_schedule(self, dst=None, src=None, name=None):
        """Copy values of one schedule in another schedule.

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
            dst = self.current_schedule
        elif src is None:
            src = self.current_schedule
        src_schedule = self.schedules[src]
        if name is None:
            self.schedules[dst] = {key: entries.copy() for key, entries in src_schedule.items()}
        else:
            if dst not in self.schedules:
                self.new_schedule(dst)
            self.schedules[dst][name] = src_schedule[name].copy()
        for e in self.get_lower_entities():
            e.copy_schedule(dst, src, name)

    def load_schedule(self, schedule): # TODO add warm start capability
        """Copy values of one schedule in another schedule.

        Parameters
        ----------
        schedule : str
        Name of schedule to set as current schedule.
        """
        self.current_schedule = schedule
        for e in self.get_lower_entities():
            e.load_schedule(schedule)

    @property
    def schedule(self):
        return self.schedules[self.current_schedule]

    def __getattr__(self, item):
        if type(item) == str:
            items = item.split("_")
            if len(items) >= 2:
                if "Schedule" == items[-1]:
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
        if type(attr) == str:
            attrs = attr.split("_")
            if len(attrs) >= 2:
                if "Schedule" == attrs[-1]:
                    if attrs[-2] in self.schedules and "_".join(attrs[:-2]) in self.schedule:
                        schedule = self.schedules[attrs[-2]]
                        varname = "_".join(attrs[:-2])
                    else:
                        schedule = self.schedule
                        varname = "_".join(attrs[:-1])
                    schedule[varname] = value
                    return
        super().__setattr__(attr, value)
