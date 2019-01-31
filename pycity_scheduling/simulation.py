from pycity_scheduling.algorithms import algorithms
from pycity_scheduling.util import populate_models


def run_simulation(city_district, algorithm="admm", models=None):
    """Run a Simulation.

    Parameters
    ----------
    city_district : CityDistrict
    algorithm : str
        Define which algorithm to use. Must be one of "admm", "stand-alone",
        "local", "central" or "dual-decompostition".
    models : dict, optional
        Contains one or more `gurobi.Model` for the scheduling.
    """
    # Setup
    timer = city_district.timer
    if models is None:
        models = populate_models(city_district, algorithm)
    optim_algorithm = algorithms[algorithm]

    timer.reset()
    city_district.reset()

    mpc_iterations = 0

    while (timer.currentTimestep + timer.timestepsUsedHorizon
           <= timer.simu_horizon):
        mpc_iterations += 1
        optim_algorithm(city_district, models)
        t1 = timer.currentTimestep
        t2 = timer.currentTimestep + timer.mpc_step_width
        for entity in city_district.get_lower_entities():
            entity.simulate()
            city_district.P_El_Actual_Schedule[t1:t2] += \
                entity.P_El_Actual_Schedule[t1:t2]

        timer.mpc_update()
