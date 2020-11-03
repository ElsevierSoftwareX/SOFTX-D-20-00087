"""
The pycity_scheduling framework


@institution:
Institute for Automation of Complex Power Systems (ACS)
E.ON Energy Research Center
RWTH Aachen University

@author:
Sebastian Schwarz, M.Sc.
Sebastian Alexander Uerlich, B.Sc.
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo

from pycity_scheduling.classes.city_district import CityDistrict
from pycity_scheduling.algorithms.local_optimization_algorithm import LocalOptimization


class StandAlone(LocalOptimization):
    """Implementation of the reference optimization algorithm.

    Schedule all entities in `city_district` on their own.

    """
    def _add_objective(self):
        for node, entity in zip(self.nodes, self.entities):
            if not isinstance(entity, CityDistrict):
                node.model.o = pyomo.Objective(expr=node.model.beta * pyomo.quicksum(ent.get_objective()
                                                                                     for ent in entity.get_entities()))
            else:
                node.model.o = pyomo.Objective(expr=0)
        return
