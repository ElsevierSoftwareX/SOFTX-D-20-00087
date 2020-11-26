"""
The pycity_scheduling framework


Copyright (C) 2020,
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
import pycity_base.classes.supply.electrical_heater as eh

from pycity_scheduling.util.generic_constraints import LowerActivationLimit
from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating
from pycity_scheduling.classes.electrical_entity import ElectricalEntity


class ElectricalHeater(ThermalEntityHeating, ElectricalEntity, eh.ElectricalHeater):
    """
    Extension of pyCity_base class ElectricalHeater for scheduling purposes.

    Parameters
    ----------
    environment : pycity_scheduling.classes.Environment
        Common to all other objects. Includes time and weather instances.
    p_th_nom : float
        Nominal thermal power output in [kW].
    eta : float, optional
        Efficiency of the electrical heater. Defaults to one.
    lower_activation_limit : float, optional (only adhered to in integer mode)
        Must be in [0, 1]. Lower activation limit of the electrical heater
        as a percentage of the rated power. When the electrical heater is
        in operation, its power must be zero or between the lower activation
        limit and its rated power.

        - `lower_activation_limit = 0`: Linear behavior
        - `lower_activation_limit = 1`: Two-point controlled

    Notes
    -----
    - EHs offer sets of constraints for operation. In the `convex` mode the
      following constraints and bounds are generated by the EH:

    .. math::
        0 \\geq p_{th\\_heat} &\\geq& -p_{th\\_nom} \\\\
        \\eta * p_{el} &=& - p_{th\\_heat}

    - See also:
        - pycity_scheduling.util.generic_constraints.LowerActivationLimit: Generates additional constraints for the
          `lower_activation_limit` in `integer` mode.
    """

    def __init__(self, environment, p_th_nom, eta=1, lower_activation_limit=0):
        # Flow temperature of 55 C
        super().__init__(environment, p_th_nom*1000, eta, 85, lower_activation_limit)
        self._long_id = "EH_" + self._id_string
        self.p_th_nom = p_th_nom
        self.activation_constr = LowerActivationLimit(self, "p_th_heat", lower_activation_limit, -p_th_nom)

    def populate_model(self, model, mode="convex"):
        """
        Add device block to pyomo ConcreteModel.

        Call parent's `populate_model` method and set thermal variables upper
        bounds to `self.p_th_nom`. Also add constraint to bind electrical
        demand to thermal output.

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
            m.p_th_heat_vars.setlb(-self.p_th_nom)
            m.p_th_heat_vars.setub(0.0)

            def p_coupl_rule(model, t):
                return - model.p_th_heat_vars[t] == self.eta * model.p_el_vars[t]
            m.p_coupl_constr = pyomo.Constraint(m.t, rule=p_coupl_rule)

            self.activation_constr.apply(m, mode)

        else:
            raise ValueError(
                "Mode %s is not implemented by class ElectricalHeater." % str(mode)
            )
        return
