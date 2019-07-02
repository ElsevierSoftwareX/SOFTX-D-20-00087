

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
        return self.timer.timestepsUsedHorizon

    @property
    def op_time_vec(self):
        return range(self.timer.timestepsUsedHorizon)

    @property
    def simu_horizon(self):
        return self.timer.simu_horizon

    @property
    def simu_time_vec(self):
        return range(self.timer.simu_horizon)

    @property
    def time_slot(self):
        return self.timer.time_slot

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
