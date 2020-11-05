"""
The pycity_scheduling framework


Institution
-----------
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors
-------
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import matplotlib.pyplot as plt

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *


# This is a very simple power scheduling example using the central optimization algorithm to demonstrate the impact
# of system level objective "max-consumption".


def main(do_plot=False):
    print("\n\n------ Example 08: Objective Max-Consumption ------\n\n")

    # Define timer, price, weather, and environment objects:
    t = Timer(op_horizon=96, step_size=900, initial_date=(2015, 4, 1))
    p = Prices(timer=t)
    w = Weather(timer=t)
    e = Environment(timer=t, weather=w, prices=p)

    # City district with district operator objective "max-consumption":
    cd = CityDistrict(environment=e, objective='max-consumption')

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
    results = opt.solve()
    cd.copy_schedule("max-consumption")

    # Print and show the city district's schedule:
    print("Schedule of the city district:")
    print(list(cd.p_el_schedule))
    plt.plot(cd.p_el_schedule)
    plt.ylim([-2.0, 5.0])
    plt.xlabel('Time in hours')
    plt.ylabel('Electrical power in kW')
    plt.title('City district scheduling result')
    plt.grid()
    if do_plot:
        plt.show()
    return


# Conclusions:
# Using "max-consumption" as the system level objective results in a power profile with the smallest peak power for the
# considered city district over time. In other words, this means that a certain electrical power threshold at the city
# district's connection point is not exceeded by taking advantage of the local flexibility of the buildings' assets. A
# power profile with a small peak power (which is most certainly a "flat" power profile) is usually the preferred system
# operation from the viewpoint of a network operator and/or district operator.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
