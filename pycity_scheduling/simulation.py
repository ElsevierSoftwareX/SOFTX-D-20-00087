from pycity_scheduling.algorithms import algorithms
from pycity_scheduling.util import populate_models


def run_simulation(city_district, algorithm='exchange-admm', models=None,
                   mode='full', robustness=None, debug=True):
    """Run a simulation for the complete horizon.

    Parameters
    ----------
    city_district : CityDistrict
    algorithm : {"admm", "stand-alone", "local", "central"}, optional
        Define which algorithm to use.
    models : dict of gurobipy.Model, optional
        Models for each node for the scheduling.
    mode : str, optional
        If 'full' use all possibilities to minimize adjustments.
        Else do not try to compensate adjustments.
    robustness : tuple, optional
        Tuple of two floats. First entry defines how many time steps are
        protected from deviations. Second entry defines the magnitude of
        deviations which are considered.
    debug : bool, optional
        Specify wether detailed debug information shall be printed.
    """
    # Setup
    ti = city_district.timer
    if models is None:
        models = populate_models(city_district, algorithm)
    optim_algorithm = algorithms[algorithm]

    ti.reset()
    city_district.reset()

    while ti.currentTimestep + ti.timestepsUsedHorizon <= ti.simu_horizon:
        optim_algorithm(city_district, models,
                        robustness=robustness, debug=debug)
        t1 = ti.currentTimestep
        t2 = ti.currentTimestep + ti.mpc_step_width
        for entity in city_district.get_lower_entities():
            entity.simulate(mode, debug)
            city_district.P_El_Act_Schedule[t1:t2] += \
                entity.P_El_Act_Schedule[t1:t2]

        ti.mpc_update()
