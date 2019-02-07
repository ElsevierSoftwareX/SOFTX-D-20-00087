from .block_computation import compute_blocks, compute_inverted_blocks
from .populate_models import populate_models
from .write_csv import schedule_to_csv
from .factory import (generate_standard_environment, generate_tabula_buildings,
                      generate_tabula_district,)


__all__ = [
    "compute_blocks",
    "compute_inverted_blocks",
    "populate_models",
    "schedule_to_csv",
    "generate_standard_environment",
    "generate_tabula_buildings",
    "generate_tabula_district",
    "get_normal_params",
]


def get_normal_params(sigma_lognormal):
    """Calculates the sigma and my for a normal distribution.

    Calculates the sigma and my for the normal distribution, which lead to a
    sigma as specified and a my of 1 for the corresponding lognormal
    distribution.

    Parameters
    ----------
    sigma_lognormal : float
        Sigma of the lognormal distribution.

    Returns
    -------
    float :
        Sigma of the normal distribution.
    float :
        My of the normal distribution.
    """
    import math
    sigma_normal = math.sqrt(math.log(sigma_lognormal**2+1))
    my_normal = -sigma_normal**2/2
    return sigma_normal, my_normal
