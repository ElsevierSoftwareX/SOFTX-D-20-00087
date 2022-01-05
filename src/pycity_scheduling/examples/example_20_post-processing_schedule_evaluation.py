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

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *
from pycity_scheduling.util.plot_schedules import plot_entity, plot_imbalance, plot_entity_directory
from pycity_scheduling.util.write_schedules import schedule_to_json, schedule_to_csv


# This examples demonstrates some post-processing capabilities of the pycity_scheduling framework.


def main(do_plot=False):
    print("\n\n------ Example 20: Post-Processing Schedule Evaluation ------\n\n")

    # Define timer, price, weather, and environment objects:
    t = Timer()
    p = Prices(timer=t)
    w = Weather(timer=t)
    e = Environment(timer=t, weather=w, prices=p)

    # City district with district operator objective "peak-shaving":
    cd = CityDistrict(environment=e, objective='peak-shaving')

    # Schedule two sample buildings. The buildings' objectives are defined as "peak-shaving".

    # Building no. one comes with fixed load, space heating, electrical heater, pv unit, thermal energy storage, and
    # electrical battery energy storage:
    bd1 = Building(environment=e, objective='peak-shaving')
    cd.addEntity(entity=bd1, position=[0, 0])
    bes = BuildingEnergySystem(environment=e)
    bd1.addEntity(bes)
    ths = ThermalHeatingStorage(environment=e, e_th_max=40, soc_init=0.5)
    bes.addDevice(ths)
    eh = ElectricalHeater(environment=e, p_th_nom=10)
    bes.addDevice(eh)
    ap = Apartment(environment=e)
    bd1.addEntity(ap)
    load = np.array(-np.sin(np.linspace(0, 2.1*np.pi, 96)+1))
    fi = FixedLoad(e, method=0, demand=load)
    ap.addEntity(fi)
    sh = SpaceHeating(environment=e, method=0, loadcurve=load)
    ap.addEntity(sh)
    pv = Photovoltaic(environment=e, method=1, peak_power=4.6)
    bes.addDevice(pv)
    bat = Battery(environment=e, e_el_max=4.8, p_el_max_charge=3.6, p_el_max_discharge=3.6)
    bes.addDevice(bat)

    # Building no. two comes with deferrable load, curtailable load, space heating, chp unit, thermal energy storage and
    # an electrical vehicle:
    bd2 = Building(environment=e, objective='peak-shaving')
    cd.addEntity(entity=bd2, position=[0, 0])
    bes = BuildingEnergySystem(environment=e)
    bd2.addEntity(bes)
    ths = ThermalHeatingStorage(environment=e, e_th_max=35, soc_init=0.5)
    bes.addDevice(ths)
    chp = CombinedHeatPower(environment=e, p_th_nom=20.0)
    bes.addDevice(chp)
    ap = Apartment(environment=e)
    bd2.addEntity(ap)
    load = np.array(-2*np.sin(np.linspace(0, 1.9*np.pi, 96)+3))
    dl = DeferrableLoad(environment=e, p_el_nom=2.0, e_consumption=2.0)
    ap.addEntity(dl)
    cl = CurtailableLoad(environment=e, p_el_nom=1.6, max_curtailment=0.8)
    ap.addEntity(cl)
    sh = SpaceHeating(environment=e, method=0, loadcurve=load)
    ap.addEntity(sh)
    ev = ElectricalVehicle(environment=e, e_el_max=37.0, p_el_max_charge=22.0, soc_init=0.65)
    ap.addEntity(ev)

    # Perform the local scheduling:
    opt = LocalOptimization(city_district=cd)
    opt.solve()
    cd.copy_schedule("ref")

    # Perform the actual scheduling:
    opt = CentralOptimization(city_district=cd)
    opt.solve(beta=0.01)
    cd.copy_schedule("central")

    if not do_plot:
        fig, ax = plt.subplots()
        kwargs = {'ax': ax}
    else:
        kwargs = {}


    # As the power generation of a PV unit cannot be altered by the algorithms when force_renewables is not set to True,
    # the schedule is the same for 'ref' and 'default'.
    if do_plot:
        plot_entity(pv, schedule=["ref", "default"], **kwargs)

    # When the city district objective is not considered in the scheduling (= uncoordinated reference case), the
    # electricity schedule of the city district is usually not balanced. This is not the case for the coordinated case
    # ("default")
    if do_plot:
        plot_entity(cd, schedule=["ref", "default"], **kwargs)

    # Additionally to this detail in the plots, you can notice that all the buildings have a constant p_th_heat_schedule
    # of zero. This is the result of all buildings satisfying a net thermal demand of zero.
    if do_plot:
        plot_entity(bd1, schedule=["ref", "default"], **kwargs)
        plot_entity(bd2, schedule=["ref", "default"], **kwargs)

    # The CHP unit has the optional integer variable p_th_Heat_state. Even when the integer mode is not used as in this
    # example, the schedule for this variable is still provided. For this variable, the value is always rounded to zero
    # if it is close enough to zero.
    if do_plot:
        plot_entity(chp, schedule=["ref", "default"], **kwargs)

    # The electrical vehicle and battery objects also have an integer variable. This variable indicates if the battery
    # is either charging or discharging/not charging.
    if do_plot:
        plot_entity(ev, schedule=["ref", "default"], **kwargs)

    # The imbalance for the city district schedule in respect to the two buildings' schedules is rather large for the
    # default schedule. This is because of the relatively large eps_primal value for the ADMM algorithm in this example.
    if do_plot:
        plot_imbalance(cd, schedule=["ref", "default"], **kwargs)

    # Since a building is always solved in one solver instance for the ADMM algorithm, its individual imbalance is
    # small, though. A solver with a large primal feasibility tolerance could, however, yield larger imbalances.
    if do_plot:
        plot_imbalance(bd1, schedule=["ref", "default"], **kwargs)


    # If required, the schedules can also be saved as .json or .csv files:
    save_schedule = do_plot

    if save_schedule:
        entities = list(cd.get_all_entities())
        schedule_to_csv(entities, file_name="example_19", schedule=["ref", "default"])
        schedule_to_json(entities, file_name="example_19", schedule=["ref", "default"])

        # Plot the city district hierarchy and its lower-level devices into the current directory:
        plot_entity_directory(cd, ["ref", "default"], levels=2)
    return


# Conclusions:
# Useful post-processing functions, such as the plotting or exporting of power schedules can be used easily in
# framework pycity_scheduling.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
