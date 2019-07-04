import numpy as np

import pycity_scheduling.classes as classes
from pycity_scheduling.simulation import run_simulation
from pycity_scheduling.util import populate_models, factory

env = factory.generate_standard_environment(step_size=900, op_horizon=4,
                                            mpc_horizon=8, mpc_step_width=2)
env.prices.tou_prices = np.array([10]*4 + [20]*4)

district = classes.CityDistrict(env)
bd = factory.generate_simple_building(env, fl=10, sh=10, tes=18, eh=20)

district.addEntity(bd, (0, 0))

# Set uncertainty (such a high deviation is unrealistic but good as an example)
bd.apartments[0].Th_Demand_list[0].set_new_uncertainty(np.full(8, 1.5))
bd.apartments[0].El_Demand_list[0].set_new_uncertainty(np.full(8, 1.5))


models = populate_models(district, 'exchange-admm')
run_simulation(district, 'exchange-admm', models)


np.set_printoptions(formatter={'float': '{: >8.4f}'.format})
print('Building P_El:')
print(bd.P_El_Schedule[:6])
print(bd.P_El_Act_Schedule[:6])
print('ThermalEnergyStorage SOC:')
print(bd.bes.tes.E_Th_Schedule[:6] / bd.bes.tes.E_Th_Max)
print(bd.bes.tes.E_Th_Act_Schedule[:6] / bd.bes.tes.E_Th_Max)
print('ElectricHeater P_Th:')
print(bd.bes.electricalHeater.P_Th_Schedule[:6])
print(bd.bes.electricalHeater.P_Th_Act_Schedule[:6])
print('SpaceHeating P_Th:')
print(bd.apartments[0].Th_Demand_list[0].P_Th_Schedule[:6])
print(bd.apartments[0].Th_Demand_list[0].P_Th_Act_Schedule[:6])
print('FixedLoad P_El:')
print(bd.apartments[0].El_Demand_list[0].P_El_Schedule[:6])
print(bd.apartments[0].El_Demand_list[0].P_El_Act_Schedule[:6])
