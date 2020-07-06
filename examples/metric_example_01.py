import numpy as np

import pycity_scheduling.classes as classes
import pycity_scheduling.algorithms as algs
from pycity_scheduling.util import factory
from pycity_scheduling.util.metric import calculate_costs, peak_to_average_ratio, peak_reduction_ratio

env = factory.generate_standard_environment(step_size=900, op_horizon=6)
# Make it attractive for the client to shift demand into first half of
# scheduling period
env.prices.tou_prices = np.array([10]*3 + [20]*3)

# Aggregator objective is peak-shaving
district = classes.CityDistrict(env, objective='peak-shaving')
# Fixed load of constant 10 kW, space heating with constant 10 kW load, thermal
# storage with 20 kWh, electric heater with 20 kW
# The building gets assigned a price objective automatically
bd = factory.generate_simple_building(env, fl=10, sh=10, tes=20, eh=20)

district.addEntity(bd, (0, 0))

# Pseudo scheduling where each device is scheduled on its own
algs.stand_alone_optimization(district)
# Results are now in the _Ref schedules
bd.save_ref_schedule()
# Normal scheduling with aggregator and client objectives
algs.central_optimization(district)


np.set_printoptions(formatter={'float': '{: >8.3f}'.format})
print('Comparing stand-alone with optimized case:')
print('Building P_El:')
print(bd.P_El_Ref_Schedule)
print(bd.P_El_Schedule)
print('Optimized costs:   {: >8.3f}'.format(calculate_costs(bd)))
bd.load_schedule("Ref")
print('Stand-alone costs: {: >8.3f}'
      .format(calculate_costs(bd)))
bd.load_schedule("default")
print('Optimized PAR:     {: >8.3f}'.format(peak_to_average_ratio(bd)))
bd.load_schedule("Ref")
print('Stand-alone PAR:   {: >8.3f}'
      .format(peak_to_average_ratio(bd)))
bd.load_schedule("default")
print('PRR:               {: >8.3f}'.format(peak_reduction_ratio(bd, "Ref")))
