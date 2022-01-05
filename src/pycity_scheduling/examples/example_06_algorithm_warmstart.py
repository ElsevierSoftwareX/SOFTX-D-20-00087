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
import pyomo.environ as pyomo

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *
from pycity_scheduling.solvers import *


# This examples demonstrates the warmstart capability for algorithms implemented in pycity_scheduling.


def main(do_plot=False):
    print("\n\n------ Example 06: Algorithm Warmstart ------\n\n")

    # Unfortunately, algorithm warmstart capabilities are supported by the Gurobi/CPLEX solvers only:
    if not (DEFAULT_SOLVER is "gurobi_direct" or
            DEFAULT_SOLVER is "gurobi_persistent" or
            DEFAULT_SOLVER is "cplex"):
        print("Algorithm warmstart capability supported by the Gurobi/CPLEX solvers only! Example is not executed.")
        return

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
    eh = ElectricalHeater(environment=e, p_th_nom=10, lower_activation_limit=0.25)
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
    chp = CombinedHeatPower(environment=e, p_th_nom=20.0, lower_activation_limit=0.1)
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

    # Perform the scheduling with the Exchange ADMM algorithm to obtain an algorithm warmstart point:
    opt = ExchangeADMM(city_district=cd, rho=2.0, eps_primal=1, eps_dual=1, mode="integer")
    r1 = opt.solve()
    imbalance = sum(np.abs(cd.schedule["p_el"] - bd1.schedule["p_el"] - bd2.schedule["p_el"]))

    # Let the city district account for power imbalances in order to achieve a feasible schedule.
    cd.account_imbalance()
    admm_obj_imbalance = pyomo.value(cd.get_objective() + bd1.get_objective() + bd2.get_objective())

    # Load the obtained values into the model to influence the pyomo.value parameter:
    cd.load_schedule_into_model()
    admm_obj = pyomo.value(cd.get_objective() + bd1.get_objective() + bd2.get_objective())

    # Now perform a central optimization with the given warmstart point:
    opt = CentralOptimization(city_district=cd, mode="integer",
                              solver_options={'solve': {'warmstart': True, 'tee': True}})

    # Now, explicitly load the current schedule into the model:
    cd.load_schedule_into_model()
    r2 = opt.solve()
    central_obj = pyomo.value(cd.get_objective() + bd1.get_objective() + bd2.get_objective())

    # For benchmarking, now perform the central optimization without the warmstart point, too:
    opt = CentralOptimization(city_district=cd, mode="integer")
    cd.load_schedule_into_model()
    r3 = opt.solve()

    admm_parallel_time = r1["times"][-1] - sum(sum(dt.values()) - max(dt.values()) for dt in r1["distributed_times"])
    print("Iterations of ADMM algorithm:                       {: >8}".format(r1["iterations"][-1]))
    print("Total time of ADMM algorithm:                       {: >8.3f}".format(r1["times"][-1]))
    print("Time of ADMM algorithm in 'parallel':               {: >8.3f}".format(admm_parallel_time))
    print("Remaining imbalance of ADMM algorithm:              {: >8.3f}".format(imbalance))
    print("Time of central algorithm with ADMM warmstart:      {: >8.3f}".format(r2["times"][-1]))
    print("Time of central algorithm without ADMM warmstart:   {: >8.3f}".format(r3["times"][-1]))
    print("Objective value of ADMM algorithm with imbalance:   {: >8.3f}".format(admm_obj_imbalance))
    print("Objective value of ADMM algorithm:                  {: >8.3f}".format(admm_obj))
    print("Objective value of central algorithm:               {: >8.3f}".format(central_obj))
    return


# Conclusions:
# The algorithm warm-start capability is a good opportunity to increase the solution speed especially for centralized
# optimization algorithms, as all variables are already pre-initialized with a solution that is located "close" to the
# actual optimum. In particular, using the warm-start capability is reasonable for large problems (i.e., city districts
# that may contain hundreds of buildings and assets).


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
