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
import matplotlib.pyplot as plt
from matplotlib import gridspec

import pycity_scheduling.util.factory as factory
from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *


# This is a simple power scheduling example to demonstrate the integration and interaction of PV and battery storage
# systems using the central optimization algorithm.


def main(do_plot=False):
    print("\n\n------ Example 17: Scheduling PV+Battery System ------\n\n")

    # Scheduling will be performed for one month:
    env = factory.generate_standard_environment(step_size=3600, op_horizon=24*31, mpc_horizon=None,
                                                mpc_step_width=None, initial_date=(2018, 3, 1), initial_time=(0, 0, 0))

    # City district / district operator objective is peak-shaving:
    cd = CityDistrict(environment=env, objective='peak-shaving')

    # Building equipped with an inflexible load and a PV+battery system / building objective is peak-shaving:
    bd = Building(environment=env, objective='peak-shaving')
    cd.addEntity(entity=bd, position=[0, 0])
    ap = Apartment(environment=env)
    bd.addEntity(ap)
    fl = FixedLoad(environment=env, method=1, annual_demand=3500.0, profile_type="H0")
    ap.addEntity(fl)
    bes = BuildingEnergySystem(environment=env)
    bd.addEntity(bes)
    pv = Photovoltaic(environment=env, method=0, area=25.0, beta=30.0, eta_noct=0.15)
    bes.addDevice(pv)
    bat = Battery(environment=env, e_el_max=13.6, p_el_max_charge=24.0, p_el_max_discharge=3.6, soc_init=0.5, eta=1,
                  storage_end_equality=True)
    bes.addDevice(bat)

    # Perform the scheduling:
    opt = CentralOptimization(city_district=cd)
    results = opt.solve()
    cd.copy_schedule("central")

    # Plot the (thermal) schedules of interest:
    plot_time = list(range(env.timer.timesteps_used_horizon))

    gs = gridspec.GridSpec(5, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(plot_time, bd.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.ylim([-15, 15])
    plt.grid()
    plt.title("Schedules")
    plt.ylabel("Building [kW]")

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(plot_time, pv.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("PV [kW]")

    ax2 = plt.subplot(gs[2], sharex=ax0)
    ax2.plot(plot_time, fl.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Load [kW]")

    ax3 = plt.subplot(gs[3], sharex=ax0)
    ax3.plot(plot_time, bat.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Battery [kW]")

    ax4 = plt.subplot(gs[4], sharex=ax0)
    ax4.plot(plot_time, bat.e_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Battery [kWh]")

    plt.xlabel("Time", fontsize=12)

    if do_plot:
        figManager = plt.get_current_fig_manager()
        if hasattr(figManager, "window"):
            figManagerWindow = figManager.window
            if hasattr(figManagerWindow, "state"):
                figManager.window.state("zoomed")
        plt.show()
    return


# Conclusions:
# To satisfy the desired peak-shaving objectives of the local building and the city district, it becomes evident that
# the battery storage unit is scheduled in a way that power is charged during times of a PV generation surplus (i.e.,
# noon time). Vice versa, it is discharged during times of a PV generation shortage (i.e., during the night). Moreover,
# the battery storage unit is used to better cope with the fluctuating power consumption/generation inside the building.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
