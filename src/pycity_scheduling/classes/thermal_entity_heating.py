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

from pycity_scheduling.classes.optimization_entity import OptimizationEntity


class ThermalEntityHeating(OptimizationEntity):
    """
    Base class for all thermal heating entities derived from OptimizationEntity.

    This class provides functionality common to all thermal heating entities.


    Notes
    -----
    - Heating TEs add the :math:`p_{th\\_heat}` variable to the model. When not modified
      by other classes, the following constraint is added:

    .. math::
        p_{th\\_heat} \\geq 0
    """

    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)

        self.new_var("p_th_heat")

    def populate_model(self, model, mode="convex"):
        """
        Add device block to pyomo ConcreteModel.

        Add variables for the thermal heating demand of the entity to the optimization
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
        m.p_th_heat_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, None), initialize=0)
        return
