from .stand_alone_optimization_algorithm import stand_alone_optimization
from .local_optimization_algorithm import local_optimization
from .exchange_admm_algorithm import exchange_admm
from .central_optimization_algortihm import central_optimization
from .dual_decomposition_algortihm import dual_decomposition

algorithms = {
    "stand-alone": stand_alone_optimization,
    "local": local_optimization,
    "exchange-admm": exchange_admm,
    "central": central_optimization,
    "dual-decomposition": dual_decomposition,
}

__all__ = [
    "stand_alone_optimization",
    "local_optimization",
    "exchange_admm",
    "central_optimization",
    "dual_decomposition",
    "algorithms",
]
