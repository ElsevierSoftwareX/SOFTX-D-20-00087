import numpy as np

import pycity_scheduling.classes as classes
from pycity_scheduling.simulation import run_simulation
from pycity_scheduling.util import factory

env = factory.generate_standard_environment(step_size=900, op_horizon=6)
# Make it attractive to shift demand into first half of scheduling period
env.prices.tou_prices = np.array([10]*3 + [20]*3)

district = classes.CityDistrict(env)
# Fixed load of constant 10 kW, space heating with constant 10 kW load, thermal
# storage with 20 kWh, electric heater with 20 kW
bd = factory.generate_simple_building(env, fl=10, sh=10, tes=20, eh=20)

district.addEntity(bd, (0, 0))

# Set uncertainties (50% deviation is unrealistic but good as an example)
bd.apartments[0].Th_Demand_list[0].set_new_uncertainty(np.full(6, 1.5))
bd.apartments[0].El_Demand_list[0].set_new_uncertainty(np.full(6, 1.5))


run_simulation(district, 'exchange-admm')


np.set_printoptions(formatter={'float': '{: >8.4f}'.format})
print('Building P_El:')
print(bd.P_El_Schedule)
print(bd.P_El_Act_Schedule)
print('ThermalEnergyStorage E_Th:')
print(bd.bes.tes.E_Th_Schedule)
print(bd.bes.tes.E_Th_Act_Schedule)
print('ElectricHeater P_Th:')
print(bd.bes.electricalHeater.P_Th_Schedule)
print(bd.bes.electricalHeater.P_Th_Act_Schedule)
print('SpaceHeating P_Th:')
print(bd.apartments[0].Th_Demand_list[0].P_Th_Schedule)
print(bd.apartments[0].Th_Demand_list[0].P_Th_Act_Schedule)
print('FixedLoad P_El:')
print(bd.apartments[0].El_Demand_list[0].P_El_Schedule)
print(bd.apartments[0].El_Demand_list[0].P_El_Act_Schedule)
