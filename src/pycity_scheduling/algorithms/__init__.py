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


from .stand_alone_optimization_algorithm import StandAlone
from .local_optimization_algorithm import LocalOptimization
from .exchange_admm_algorithm import ExchangeADMM
from .central_optimization_algorithm import CentralOptimization
from .dual_decomposition_algorithm import DualDecomposition


__all__ = [
    'StandAlone',
    'LocalOptimization',
    'ExchangeADMM',
    'CentralOptimization',
    'DualDecomposition',
    'algorithm',
    'algorithms',
]


algorithms = {
    'stand-alone': StandAlone,
    'local': LocalOptimization,
    'exchange-admm': ExchangeADMM,
    'central': CentralOptimization,
    'dual-decomposition': DualDecomposition,
}
