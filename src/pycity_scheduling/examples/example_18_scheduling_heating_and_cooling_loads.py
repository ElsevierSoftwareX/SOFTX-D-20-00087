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


# This is a simple power scheduling example to demonstrate the integration and impact of building cooling and
# heating loads using the central optimization algorithm.


def main(do_plot=False):
    print("\n\n------ Example 18: Scheduling Heating and Cooling Loads ------\n\n")

    # Scheduling will be performed for a full year:
    env = factory.generate_standard_environment(step_size=3600, op_horizon=24*365, mpc_horizon=None,
                                                mpc_step_width=None, initial_date=(2018, 1, 1), initial_time=(0, 0, 0))

    # Use a standardized thermal load profile for space heating and then 'convert' it into a cooling load
    # (inverted load assumption according to pycity_base):
    sh_slp = SpaceHeating(environment=env, method=1, living_area=150, specific_demand=50)

    sc_slp = SpaceCooling(environment=env,
                          method=0,
                          loadcurve=np.ones(env.timer.timesteps_total)*max(sh_slp.get_power()) / 1000.0 - sh_slp.
                          get_power() / 1000.0)

    # Plot the thermal loads:
    plot_time = list(range(env.timer.timesteps_used_horizon))

    gs = gridspec.GridSpec(2, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(plot_time, sh_slp.p_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.ylabel("Space Heating [kW]")

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(plot_time, sc_slp.p_th_cool_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Space Cooling [kW]")
    plt.title("Thermal Load Profiles")
    plt.grid()
    if do_plot:
        figManager = plt.get_current_fig_manager()
        if hasattr(figManager, "window"):
            figManagerWindow = figManager.window
            if hasattr(figManagerWindow, "state"):
                figManager.window.state("zoomed")
        plt.show()


    # Now perform the scheduling of two buildings, where the first building is equipped with the heating load and
    # a thermal heating system and the second building is equipped with the cooling load and a thermal cooling system.

    # City district with district operator objective "price":
    cd = CityDistrict(environment=env, objective='max-consumption')

    # Building no. one with building objective price:
    bd1 = Building(environment=env, objective='price')
    cd.addEntity(entity=bd1, position=[0, 0])
    bes = BuildingEnergySystem(environment=env)
    bd1.addEntity(bes)
    ths = ThermalHeatingStorage(environment=env, e_th_max=16.0, soc_init=0.5, loss_factor=0.05)
    bes.addDevice(ths)
    hp = HeatPump(environment=env, p_th_nom=8.0)
    bes.addDevice(hp)
    ap = Apartment(environment=env)
    bd1.addEntity(ap)
    ap.addEntity(sh_slp)

    # Building no. two with building objective co2:
    bd2 = Building(environment=env, objective='co2')
    cd.addEntity(entity=bd2, position=[0, 1])
    bes = BuildingEnergySystem(environment=env)
    bd2.addEntity(bes)
    tcs = ThermalCoolingStorage(environment=env, e_th_max=10.0, soc_init=0.5, loss_factor=0.1)
    bes.addDevice(tcs)
    ch = Chiller(environment=env, p_th_nom=5.0, cop=3.5)
    bes.addDevice(ch)
    ap = Apartment(environment=env)
    bd2.addEntity(ap)
    ap.addEntity(sc_slp)

    # Perform the scheduling:
    opt = CentralOptimization(city_district=cd)
    results = opt.solve()
    cd.copy_schedule("central")

    # Plot the (thermal) schedules of interest:
    plot_time = list(range(env.timer.timesteps_used_horizon))

    gs = gridspec.GridSpec(4, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(plot_time, -hp.p_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.ylim([-15, 15])
    plt.grid()
    plt.title("Thermal Schedules")
    plt.ylabel("Heat Pump [kW]")

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(plot_time, ths.e_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Heating Storage [kWh]")

    ax2 = plt.subplot(gs[2], sharex=ax0)
    ax2.plot(plot_time, -ch.p_th_cool_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Chiller [kW]")

    ax3 = plt.subplot(gs[3], sharex=ax0)
    ax3.plot(plot_time, tcs.e_th_cool_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Cooling Storage [kWh]")

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
# In analogy to the previous example (compare example_16_scheduling_pv+battery_system.py), also thermal energy storage
# units can be used as a buffer inside a sector-coupled energy system to provide flexibility to the local electrical
# system. In this example, for instance, the thermal heating and cooling storage units are used to (partly) decouple the
# heating respectively cooling system's thermal generation from its electrical consumption. Thus, it becomes evident
# that one can take advantage from the thermal flexibility to achieve the given local and system level scheduling
# objectives, too.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
