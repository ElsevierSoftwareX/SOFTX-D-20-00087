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

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *


# This is a very simple power scheduling example using the central optimization algorithm to demonstrate the impact
# of system level objective "price".


def main(do_plot=False):
    print("\n\n------ Example 10: Objective Price ------\n\n")

    # Define timer, price, weather, and environment objects:
    t = Timer(op_horizon=96, step_size=900, initial_date=(2015, 4, 1))
    p = Prices(timer=t)
    w = Weather(timer=t)
    e = Environment(timer=t, weather=w, prices=p)

    # City district with district operator objective "peak-shaving":
    cd = CityDistrict(environment=e, objective='price')

    # Schedule some sample buildings. The buildings' objectives are defined as "none".
    n = 10
    for i in range(n):
        bd = Building(environment=e, objective='none')
        cd.addEntity(entity=bd, position=[0, i])
        bes = BuildingEnergySystem(environment=e)
        bd.addEntity(bes)
        ths = ThermalHeatingStorage(environment=e, e_th_max=40, soc_init=0.5)
        bes.addDevice(ths)
        eh = ElectricalHeater(environment=e, p_th_nom=10)
        bes.addDevice(eh)
        ap = Apartment(environment=e)
        bd.addEntity(ap)
        fi = FixedLoad(e, method=1, annual_demand=3000.0, profile_type='H0')
        ap.addEntity(fi)
        sh = SpaceHeating(environment=e, method=1, living_area=120, specific_demand=90, profile_type='HEF')
        ap.addEntity(sh)
        pv = Photovoltaic(environment=e, method=1, peak_power=8.2)
        bes.addDevice(pv)
        bat = Battery(environment=e, e_el_max=12.0, p_el_max_charge=4.6, p_el_max_discharge=4.6)
        bes.addDevice(bat)


    # Perform the scheduling:
    opt = CentralOptimization(city_district=cd)
    opt.solve()
    cd.copy_schedule("price")

    # Print and show the city district's schedule:
    print("Schedule of the city district:")
    print(list(cd.p_el_schedule))

    gs = gridspec.GridSpec(2, 1)
    ax0 = plt.subplot(gs[0])
    ax0.plot(list(range(e.timer.timesteps_used_horizon)), cd.p_el_schedule)
    plt.ylim([-100.0, 200.0])
    plt.ylabel('Electrical power in kW')
    plt.title('City district scheduling result')

    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.plot(list(range(e.timer.timesteps_used_horizon)), e.prices.da_prices)
    plt.ylabel('Spot market day-ahead prices in ct/kWh')

    plt.xlabel('Time in hours', fontsize=12)
    plt.grid()

    if do_plot:
        figManager = plt.get_current_fig_manager()
        if hasattr(figManager, "window"):
            figManagerWindow = figManager.window
            if hasattr(figManagerWindow, "state"):
                figManager.window.state("zoomed")
        plt.show()
    return


# Conclusions:
# Using "price" as the system level objective results in a "cheap" power profile for the considered city district.
# In other words, this means that power is bought from the spot market during cheap tariff periods and sold during
# expensive tariff periods incorporating the local flexibility potentials. A cost-optimal power profile is usually
# the preferred option by a district operator who procures the electrical power for its customers.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
