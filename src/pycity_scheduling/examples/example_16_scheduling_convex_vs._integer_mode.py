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


# This is a simple power scheduling example to demonstrate the difference between the pycity_scheduling's convex and
# integer (MIP) optimization models using the distributed Exchange ADMM algorithm.


def main(do_plot=False):
    print("\n\n------ Example 16: Scheduling Convex vs. Integer Mode ------\n\n")

    # Scheduling will be performed for a typical winter day within the annual heating period:
    env = factory.generate_standard_environment(step_size=3600, op_horizon=24, mpc_horizon=None, mpc_step_width=None,
                                                initial_date=(2010, 2, 10), initial_time=(0, 0, 0))

    # City district / district operator objective is peak-shaving:
    cd = CityDistrict(environment=env, objective='peak-shaving')

    # Building equipped with space heating, electrical heater, thermal energy storage, and photovoltaic unit.
    # Objective is peak-shaving:
    bd1 = Building(environment=env, objective='peak-shaving')
    cd.addEntity(entity=bd1, position=[0, 0])
    ap1 = Apartment(environment=env)
    bd1.addEntity(ap1)
    sh1 = SpaceHeating(environment=env, method=1, living_area=120.0, specific_demand=85.9, profile_type='HEF')
    ap1.addEntity(sh1)
    bes1 = BuildingEnergySystem(environment=env)
    bd1.addEntity(bes1)
    eh1 = ElectricalHeater(environment=env, p_th_nom=12.0, lower_activation_limit=0.5)
    bes1.addDevice(eh1)
    ths1 = ThermalHeatingStorage(environment=env, e_th_max=24.0)
    bes1.addDevice(ths1)
    pv1 = Photovoltaic(environment=env, method=1, peak_power=25.0)
    bes1.addDevice(pv1)


    # First, perform the power scheduling using convex models for the electrical appliances:
    opt = ExchangeADMM(cd, mode='convex')
    opt.solve()
    cd.copy_schedule("convex_schedule")

    # Plot the convex schedules:
    plot_time = list(range(env.timer.timesteps_used_horizon))

    gs = gridspec.GridSpec(5, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(plot_time, cd.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.ylim([-15, 15])
    plt.grid()
    plt.title("Convex Schedules")
    plt.ylabel("District [kW]")

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(plot_time, pv1.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("PV [kW]")

    ax2 = plt.subplot(gs[2], sharex=ax0)
    ax2.plot(plot_time, sh1.p_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Space Heating Demand [kW]")

    ax3 = plt.subplot(gs[3], sharex=ax0)
    ax3.plot(plot_time, eh1.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("El. Heater [kW]")

    ax4 = plt.subplot(gs[4], sharex=ax0)
    ax4.plot(plot_time, ths1.e_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("THS SoC [kWh]")

    plt.xlabel("Time", fontsize=12)

    if do_plot:
        figManager = plt.get_current_fig_manager()
        if hasattr(figManager, "window"):
            figManagerWindow = figManager.window
            if hasattr(figManagerWindow, "state"):
                figManager.window.state("zoomed")
        plt.show()

    # Second, perform the power scheduling using integer models for the electrical appliances:
    opt = ExchangeADMM(cd, mode='integer')
    opt.solve()
    cd.copy_schedule("integer_schedule")

    # Plot the integer schedules:
    gs = gridspec.GridSpec(5, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(plot_time, cd.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.ylim([-15, 15])
    plt.grid()
    plt.title("Integer Schedules")
    plt.ylabel("District [kW]")

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(plot_time, pv1.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("PV [kW]")

    ax2 = plt.subplot(gs[2], sharex=ax0)
    ax2.plot(plot_time, sh1.p_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("Space Heating Demand [kW]")

    ax3 = plt.subplot(gs[3], sharex=ax0)
    ax3.plot(plot_time, eh1.p_el_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("El. Heater [kW]")

    ax4 = plt.subplot(gs[4], sharex=ax0)
    ax4.plot(plot_time, ths1.e_th_heat_schedule)
    plt.xlim((0, env.timer.timesteps_used_horizon - 1))
    plt.grid()
    plt.ylabel("THS SoC [kWh]")

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
# In the convex case, the peak-shaving objective can be fully satisfied, which becomes evident from the "flat" power
# profile of the obtained city district power curve. To perfectly balance the power demand and supply in the district,
# the flexibility from the thermal heating storage unit is exploited together with the capability to operate the
# electrical heater at any operation point between 0% and 100% of its nominal power. Instead, in the integer case, the
# electrical heater can only operate at either 0% or in-between 50% and 100% of its nominal power. For this reason, the
# final power profile on the city district level is not as "flat" as in the convex case. However, the integer case
# might better reflect the actual operation conditions of a real electrical heater unit.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
