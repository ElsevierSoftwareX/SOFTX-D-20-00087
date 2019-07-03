

class OptimizationEntity(object):
    """
    Base class for all optimization entities.

    This class provides functionalities common to all entities which take part
    in the scheduling optimization.
    """

    static_entity_id = 0

    def __init__(self, timer, *args, **kwargs):
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

        self.timer = timer
        super(OptimizationEntity, self).__init__(*args, **kwargs)

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
        raise NotImplementedError

    def update_model(self, model, mode=""):
        pass

    def update_schedule(self):
        """Update the schedule with the scheduling model solution.

        Retrieve the solution from the scheduling model and write it to the
        schedule. The model must be optimal. The time / position of the
        solution in the schedule is determined by `self.timer.currentTimestep`.
        """
        raise NotImplementedError

    def get_objective(self, coeff=1):
        return None

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        raise NotImplementedError

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
        raise NotImplementedError

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

    def update_actual_schedule(self, timestep):
        """Update the actual schedule with the deviation model solution.

        Parameters
        ----------
        timestep : int
            Current timestep of simulation.
        """
        raise NotImplementedError

    def reset(self, schedule=True, actual=True, reference=False):
        pass

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
