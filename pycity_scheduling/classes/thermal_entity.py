import numpy as np
import pyomo.environ as pyomo

from .optimization_entity import OptimizationEntity


class ThermalEntity(OptimizationEntity):
    """
    Base class for all thermal entities derived from OptimizationEntity.

    This class provides functionality common to all thermal entities.
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("P_Th")

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel.

        Add variables for the thermal demand of the entity to the optimization
        model.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        m = self.model
        m.P_Th_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)
