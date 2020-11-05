"""
:::::::::::::::::::::::::::::::::::::::
::: The pycity_scheduling Framework :::
:::::::::::::::::::::::::::::::::::::::


Institution:
::::::::::::
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
::::::::
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np

import pycity_scheduling.classes as classes
import pycity_scheduling.algorithms as algs
from pycity_scheduling.util import factory
from pycity_scheduling.util.metric import calculate_costs, peak_to_average_ratio, peak_reduction_ratio, \
                                          self_consumption, autarky, absolute_flexibility_gain


# This is a simple power scheduling example using the central optimization algorithm in order to demonstrate the
# capabilities of the pycity_scheduling framework when it comes to the evaluation of metrics. The evaluation of metrics
# is usually an important post-processing step.


def main(do_plot=False):
    print("\n\n------ Example 20: Post-Processing Metrics Evaluation ------\n\n")

    # Use a standard environment of 24 hours with hourly resolution (=60min=3600sec):
    env = factory.generate_standard_environment(step_size=3600, op_horizon=24)

    # Make it "attractive" for the consumers to shift demand into the second half of the scheduling period:
    env.prices.tou_prices = np.array([20]*12 + [10]*12)

    # City district / district operator objective is set to peak-shaving:
    cd = classes.CityDistrict(env, objective='peak-shaving')

    # The sample building in this example comes with a constant electrical and space heating load of 10kW,
    # thermal storage of capacity 20kWh and an electric heater of thermal nominal power 20kW:
    bd = factory.generate_simple_building(env, fl=10, sh=10, ths=20, eh=20)
    cd.addEntity(bd, (0, 0))

    # Perform a 'pseudo' stand-alone power scheduling, where each device is scheduled on its own (=no coordination):
    o1 = algs.StandAlone(cd)
    o1.solve()

    # Results are now in the _Ref schedules:
    bd.copy_schedule("ref")
    cd.copy_schedule("ref")

    # Now perform a coordinated scheduling with district operator and customer objectives:
    o2 = algs.CentralOptimization(cd)
    o2.solve()

    # Evaluate and print different metrics:
    np.set_printoptions(formatter={'float': '{: >8.3f}'.format})
    print('Comparing stand-alone with optimized case:')
    print('Building p_el:')
    print(bd.p_el_ref_schedule)
    print(bd.p_el_schedule)
    print('Optimized costs:        {: >8.3f}'.format(calculate_costs(bd)))
    bd.load_schedule("ref")
    print('Stand-alone costs:      {: >8.3f}'
          .format(calculate_costs(bd)))
    bd.load_schedule("default")
    print('Optimized PAR:          {: >8.3f}'.format(peak_to_average_ratio(bd)))
    bd.load_schedule("ref")
    print('Stand-alone PAR:        {: >8.3f}'
          .format(peak_to_average_ratio(bd)))
    bd.load_schedule("default")
    print('PRR:                    {: >8.3f}'.format(peak_reduction_ratio(bd, "ref")))
    print('Self-consumption ratio: {: >8.3f}'.format(self_consumption(bd)))
    print('Autarky ratio:          {: >8.3f}'.format(autarky(bd)))
    print('Absolute flex. gain:    {: >8.3f}'.format(absolute_flexibility_gain(cd, "ref")))
    return


# Conclusion:
# In contrast to the uncoordinated case (stand-alone algorithm) both the total costs as well as the power peaks are
# (slightly) reduced in the coordinated case in this exemplary scheduling case. This is because of the price and
# peak-shaving objectives of the buildings and the city district. In general, the evaluation of different metrics
# constitutes a helpful step when it comes to the comparison of different city district setups and/or power scheduling
# algorithms.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
