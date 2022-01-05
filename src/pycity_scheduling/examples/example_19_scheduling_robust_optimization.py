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

import pycity_scheduling.classes as classes
from pycity_scheduling.algorithms import CentralOptimization
from pycity_scheduling.util import factory
from pycity_scheduling.util.metric import calculate_costs


# This is a simple power scheduling example combined with a Robust Optimization (RO) application.


def main(do_plot=False):
    print("\n\n------ Example 19: Scheduling Robust Optimization ------\n\n")

    # Use a simple environment of 6 hours with quarter-hourly resolution (=15min=900sec):
    env = factory.generate_standard_environment(step_size=900, op_horizon=6)

    # Make it "attractive" for the customer to shift demand into the first half of the scheduling period
    # (compare example_20_post-processing_metrics_evaluation.py):
    env.prices.tou_prices = np.array([5]*3 + [10]*3)

    district = classes.CityDistrict(env)
    # The sample building in this example comes with a constant space heating load of 10kW, thermal storage of capacity
    # 20kWh and an electric heater of thermal nominal power 20kW:
    bd = factory.generate_simple_building(env, sh=10, ths=20, eh=20)

    district.addEntity(bd, (0, 0))

    # Perform the scheduling without RO:
    opt = CentralOptimization(district, robustness=(6, 0.0))
    opt.solve(robustness=(6, 0.0))
    bd.copy_schedule("ref")

    # Protect 6 time steps and assume a maximum deviation of 50% in each time step.
    # Such a high deviation is usually unrealistic, but makes it a good example here.
    opt.solve(robustness=(6, 0.5))

    # Print schedules/results:
    # **Note:** We compare the schedules from the two performed schedulings (with/without RO) with each other.
    np.set_printoptions(formatter={'float': '{: >8.3f}'.format})
    print('Building p_el:')
    print(bd.p_el_ref_schedule)
    print(bd.p_el_schedule)
    print('ThermalEnergyStorage e_th_heat:')
    print(bd.bes.tes_units[0].e_th_heat_ref_schedule)
    print(bd.bes.tes_units[0].e_th_heat_schedule)
    print('ThermalEnergyStorage Limits:')
    print(list(bd.model.lower_robustness_bounds[:].value))
    print(list(bd.model.upper_robustness_bounds[:].value))
    print('ElectricHeater p_th_heat:')
    print(bd.bes.electrical_heaters[0].p_th_heat_ref_schedule)
    print(bd.bes.electrical_heaters[0].p_th_heat_schedule)
    print('SpaceHeating p_th_heat:')
    print(bd.apartments[0].th_heating_demand_list[0].p_th_heat_ref_schedule)
    print(bd.apartments[0].th_heating_demand_list[0].p_th_heat_schedule)
    print('Costs:')
    bd.load_schedule("ref")
    print('{:.2f}'.format(calculate_costs(bd)))
    bd.load_schedule("default")
    print('{:.2f}'.format(calculate_costs(bd)))
    return


# Conclusions:
# If Robust Optimization (RO) is applied, the flexibility of the thermal energy storage is not fully used. This is best
# seen in the first four time steps, where the state-of-charge (SOC) is lower than without the robust approach. Instead,
# the 'energy difference' is used to cater for uncertainties that may stem from an uncertain thermal demand of the
# building. As a trade-off, the RO schedule becomes always less optimal (by means of the objective value) than without
# RO. This becomes evident by the higher costs for the robust case compared to the non-robust case in this example.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
