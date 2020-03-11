import numpy as np

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

        self.timer = environment.timer
        self.schedules = {'default': {}, 'Ref': {}, 'Act': {}}

        self.vars = {}
        self.__var_funcs__ = {}
        self.current_schedule = 'default'

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
        # reset var list
        for name in self.vars.keys():
            self.vars[name] = []

    def update_model(self, model, mode=""):
        pass

    def update_schedule(self):
        """Update the schedule with the scheduling model solution.

        Retrieve the solution from the scheduling model and write it to the
        schedule. The model must be optimal. The time / position of the
        solution in the schedule is determined by `self.timer.currentTimestep`.
        """
        op_slice = self.op_slice
        for name, schedule in self.schedule.items():
            if name in self.__var_funcs__:
                func = self.__var_funcs__[name]
                values = np.fromiter((func(t) for t in self.op_time_vec), dtype=schedule.dtype)
            else:
                values = [var.X for var in self.vars[name]]
            if schedule.dtype == np.bool:
                pad = False
            else:
                pad = True
            schedule[op_slice] = np.pad(values, (0, len(schedule[op_slice]) - len(values)), mode='constant',
                                        constant_values=pad)

    def get_objective(self, coeff=1):
        return None

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        import warnings
        warnings.warn("save_ref_schedule() is deprecated; use copy_schedule() instead", DeprecationWarning)
        self.copy_schedule("Ref", "default")

    def populate_deviation_model(self, model, mode=""):
        """Add variables for this entity to the deviation model.

        Adds variables for electric and / or thermal power and - if
        applicable - a variable for the electeric or thermal energy. Since only
        one timestep is simulated only one variable per physical unit is added.

        Parameters
        ----------
        model : gurobipy.Model
            Deviation model for computing the actual schedule.
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        """
        pass

    def update_deviation_model(self, model, timestep, mode=""):
        """Update the deviation model for the current timestep.

        Parameters
        ----------
        model : gurobipy.Model
            Deviation model for computing the actual schedule.
        timestep : int
            Current timestep of simulation.
        mode : str, optional
            If 'full' use all possibilities to minimize adjustments.
            Else do not try to compensate adjustments.
        """
        pass

    def reset(self, name=None):
        if name is None:
            for name in self.schedules.keys():
                self.new_schedule(name)
        self.new_schedule(name)

    def calculate_costs(self, schedule=None, timestep=None, prices=None,
                        feedin_factor=None):
        """Calculate electricity costs for the OptimizationEntity.

        Parameters
        ----------
        schedule : str, optional
            Specify which schedule to use.
            `None` : Normal schedule
            'act', 'actual' : Actual schedule
            'ref', 'reference' : Reference schedule
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
        return 0

    def calculate_co2(self, schedule=None, timestep=None, co2_emissions=None):
        """Calculate CO2 emissions of the entity.

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
        return 0

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
        self.vars[name] = []
        if func is not None:
            self.__var_funcs__[name] = func
        for schedule in self.schedules.values():
            schedule[name] = np.full(self.timer.simu_horizon, 0, dtype=dtype)

    def new_schedule(self, schedule):
        self.schedules[schedule] = {name: np.full_like(entries, 0)for name, entries in self.current_schedule.keys()}
        for e in self.get_lower_entities():
            e.new_schedule(schedule)

    def copy_schedule(self, dst=None, src=None, name=None):
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

    def load_schedule(self, schedule):
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
                elif "vars" == items[-1]:
                    varlist = self.vars.get(item[:-5], None)
                    if varlist is not None:
                        return varlist
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
                elif "vars" == attrs[-1]:
                    self.vars[attr[:-5]] = value
        super().__setattr__(attr, value)
