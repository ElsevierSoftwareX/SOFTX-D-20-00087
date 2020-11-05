"""
:::::::::::::::::::::::::::::::::::::::
::: The pycity_scheduling Framework :::
:::::::::::::::::::::::::::::::::::::::


Institution:
::::::::::::
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
::::::::
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.classes.optimization_entity import OptimizationEntity


class ThermalEntityCooling(OptimizationEntity):
    """
    Base class for all thermal cooling entities derived from OptimizationEntity.

    This class provides functionality common to all thermal cooling entities.


    Notes
    -----
    - Cooling TEs add the :math:`p_{th\\_cool}` variable to the model. When not modified
    by other classes, the following constraint is added:

    .. math::
        p_{th\\_cool} \\geq 0
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("p_th_cool")

    def populate_model(self, model, mode="convex"):
        """
        Add device block to pyomo ConcreteModel.

        Add variables for the thermal cooling demand of the entity to the optimization
        model.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer`  : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        m = self.model
        m.p_th_cool_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)
        return
