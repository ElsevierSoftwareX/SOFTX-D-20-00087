import numpy as np

import pycity_scheduling.classes as classes
from pycity_scheduling.algorithms import central_optimization
from pycity_scheduling.util import factory
from pycity_scheduling.util.metric import calculate_costs

env = factory.generate_standard_environment(step_size=900, op_horizon=6)
# Make it attractive to shift demand into first half of scheduling period
env.prices.tou_prices = np.array([6]*3 + [10]*3)

district = classes.CityDistrict(env)
# Space heating with constant 10 kW load, thermal storage with 20 kWh,
# electric heater with 20 kW
bd = factory.generate_simple_building(env, sh=10, tes=20, eh=20)

district.addEntity(bd, (0, 0))

# Scheduling without RO
central_optimization(district)
# Results without RO are now in the _Ref schedules
bd.save_ref_schedule()
# Protect 6 time steps and assume a deviation of 50% in each time step
# Such a high deviation is unrealistic but makes for a good example.
central_optimization(district, robustness=(6, 0.5))


np.set_printoptions(formatter={'float': '{: >8.3f}'.format})
print('Building P_El:')
print(bd.P_El_Ref_Schedule)
print(bd.P_El_Schedule)
print('ThermalEnergyStorage E_Th:')
print(bd.bes.tes.E_Th_Ref_Schedule)
print(bd.bes.tes.E_Th_Schedule)
print('ThermalEnergyStorage Limits:')
print(list(bd.model.lower_robustness_bounds[:].value))
print(list(bd.model.upper_robustness_bounds[:].value))
print('ElectricHeater P_Th:')
print(bd.bes.electricalHeater.P_Th_Ref_Schedule)
print(bd.bes.electricalHeater.P_Th_Schedule)
print('SpaceHeating P_Th:')
print(bd.apartments[0].Th_Demand_list[0].P_Th_Ref_Schedule)
print(bd.apartments[0].Th_Demand_list[0].P_Th_Schedule)
print('Costs:')
bd.load_schedule("Ref")
print('{:.2f}'.format(calculate_costs(bd)))
bd.load_schedule("default")
print('{:.2f}'.format(calculate_costs(bd)))
