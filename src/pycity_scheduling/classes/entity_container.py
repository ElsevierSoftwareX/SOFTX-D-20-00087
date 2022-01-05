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

from pycity_scheduling.classes.thermal_entity_cooling import ThermalEntityCooling
from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating
from pycity_scheduling.classes.electrical_entity import ElectricalEntity


class EntityContainer(ThermalEntityCooling, ThermalEntityHeating, ElectricalEntity):
    """
    Base class for entities containing other entities.

    `p_th` and `p_el` imbalances are propagated to this entities variables.
    During calls to its scheduling functions, the contained entities are also
    called with the same parameters.

    Notes
    -----
    - EntityContainers offer sets of constraints for operation. The following
      constraints are added.

    .. math::
        p_{th\\_cool} &=& \\sum_i p_{th\\_cool\\_i} \\\\
        p_{th\\_heat} &=& \\sum_i p_{th\\_heat\\_i} \\\\
        p_{el} &=& \\sum_i p_{el\\_i}

    - :math:`p_{th\\_cool\\_i}`, :math:`p_{th\\_heat\\_i}`, and :math:`p_{el\\_i}` are the variables from lower
      entities. The Bounds from TEC, TEH, and EE are removed.
    """

    def populate_model(self, model, mode="convex"):
        """
        Add entity block and lower entities blocks to pyomo ConcreteModel.

        Call both parent's `populate_model` methods and set variables lower
        bounds to `None`. Then call `populate_model` method of all contained
        entities and add constraints that the sum of their variables for each
        period equals the corresponding own variable.

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

        if mode in ["convex", "integer"]:
            p_th_cool_var_list = []
            p_th_heat_var_list = []
            p_el_var_list = []
            for entity in self.get_lower_entities():
                entity.populate_model(model, mode)
                if isinstance(entity, ThermalEntityCooling):
                    p_th_cool_var_list.append(entity.model.p_th_cool_vars)
                if isinstance(entity, ThermalEntityHeating):
                    p_th_heat_var_list.append(entity.model.p_th_heat_vars)
                if isinstance(entity, ElectricalEntity):
                    p_el_var_list.append(entity.model.p_el_vars)

            m.p_th_cool_vars.setlb(None)
            m.p_th_heat_vars.setlb(None)
            m.p_el_vars.setlb(None)

            def p_th_cool_sum_rule(model, t):
                return model.p_th_cool_vars[t] == pyomo.quicksum(p_th_Cool_var[t] for
                                                                 p_th_Cool_var in p_th_cool_var_list)
            m.p_th_cool_constr = pyomo.Constraint(m.t, rule=p_th_cool_sum_rule)

            def p_th_heat_sum_rule(model, t):
                return model.p_th_heat_vars[t] == pyomo.quicksum(p_th_Heat_var[t] for
                                                                 p_th_Heat_var in p_th_heat_var_list)
            m.p_th_heat_constr = pyomo.Constraint(m.t, rule=p_th_heat_sum_rule)

            def p_el_sum_rule(model, t):
                return model.p_el_vars[t] == pyomo.quicksum(p_el_var[t] for p_el_var in p_el_var_list)
            m.p_el_constr = pyomo.Constraint(m.t, rule=p_el_sum_rule)
        else:
            raise ValueError(
                "Mode %s is not implemented by class EntityContainer." % str(mode)
            )
        return

    def update_model(self, mode=""):
        super().update_model(mode)
        for entity in self.get_lower_entities():
            entity.update_model(mode)
        return

    def update_schedule(self):
        super().update_schedule()
        for entity in self.get_lower_entities():
            entity.update_schedule()
        return

    def reset(self, schedule=None):
        super().reset(schedule)
        for entity in self.get_lower_entities():
            entity.reset(schedule)
        return

    def get_lower_entities(self):
        raise NotImplementedError
