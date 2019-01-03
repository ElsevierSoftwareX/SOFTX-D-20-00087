

class OptimizationEntity(object):
    """
    Base class for all optimization entities.

    This class provides functionalities common to all entities which take part
    in the scheduling optimization.
    """

    OP_HORIZON = -1
    OP_TIME_VEC = None
    SIMU_HORIZON = -1
    SIMU_TIME_VEC = None
    # MPC_HORIZON = -1
    # MPC_TIME_VEC = None
    TIME_SLOT = -1

    static_entity_id = 0

    def __init__(self, timer, *args, **kwargs):
        OptimizationEntity.static_entity_id += 1
        self.ID = OptimizationEntity.static_entity_id
        self._ID_string = "{0:05d}".format(self.ID)
        self._long_ID = ""
        self._kind = ""

        self.timer = timer
        if OptimizationEntity.OP_HORIZON == -1:
            OptimizationEntity.OP_HORIZON = timer.timestepsUsedHorizon
            OptimizationEntity.OP_TIME_VEC = range(self.OP_HORIZON)
        if OptimizationEntity.SIMU_HORIZON == -1:
            OptimizationEntity.SIMU_HORIZON = timer.simu_horizon
            OptimizationEntity.SIMU_TIME_VEC = range(self.SIMU_HORIZON)
        if OptimizationEntity.TIME_SLOT == -1:
            OptimizationEntity.TIME_SLOT = timer.timeDiscretization/3600
        super(OptimizationEntity, self).__init__(*args, **kwargs)

    def __str__(self):
        return self._long_ID

    def __repr__(self):
        return ("<OptimizationEntity of kind " + self._kind
                + " with ID: " + self._long_ID + ">")

    @property
    def MPC_HORIZON(self):
        return self.timer.mpc_step_width

    @property
    def MPC_TIME_VEC(self):
        return range(self.timer.mpc_step_width)

    def populate_model(self, model, mode=""):
        raise NotImplementedError

    def update_model(self, model, mode=""):
        pass

    def update_schedule(self, mode=""):
        raise NotImplementedError

    def set_new_uncertainty(self, unc):
        pass

    def get_objective(self, coeff=1):
        return None

    def save_ref_schedule(self):
        """Save the schedule of the current reference scheduling."""
        raise NotImplementedError

    def reset(self, schedule=True, reference=False):
        pass

    def calculate_costs(self, timestep=None, prices=None, reference=False):
        """Calculate electricity costs for the OptimizationEntity.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        prices : array_like, optional
            Energy prices for simulation horizon.
        reference : bool, optional
            `True` if costs for reference schedule.

        Returns
        -------
        float :
            Electricity costs in [ct].
        """
        return 0

    def calculate_co2(self, timestep=None, co2_emissions=None,
                      reference=False):
        """Calculate CO2 emissions of the entity.

        Parameters
        ----------
        timestep : int, optional
            If specified, calculate costs only to this timestep.
        co2_emissions : array_like, optional
            CO2 emissions for all timesteps in simulation horizon.
        reference : bool, optional
            `True` if CO2 for reference schedule.

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
