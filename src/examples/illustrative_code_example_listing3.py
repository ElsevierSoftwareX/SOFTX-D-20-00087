import matplotlib.pyplot as plt
from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *

t = Timer(op_horizon=24, step_size=3600, initial_date=(2018, 3, 15), initial_time=(0, 0, 0))
w = Weather(timer=t, location=(50.76, 6.07))
p = Prices(timer=t)
e = Environment(timer=t, weather=w, prices=p)

fi = FixedLoad(environment=e, method=1, annual_demand=3000.0, profile_type="H0")
pv = Photovoltaic(environment=e, method=1, peak_power=6.0)
ba = Battery(environment=e, e_el_max=8.4, p_el_max_charge=3.6, p_el_max_discharge=3.6)

plot_time = list(range(t. timesteps_used_horizon))
fig, axs = plt.subplots(1, 3)
axs[0].plot(plot_time, p. da_prices, color="black")
axs[0].set_title("Day-ahead energy market prices [ct/kWh]")
axs[1].plot(plot_time, fi.p_el_schedule, color="black")
axs[1].set_title("Single-family house electrical load demand [kW]")
axs[2].plot(plot_time, pv.p_el_supply, color="black")
axs[2].set_title("Residential photovoltaics generation [kW]")
for ax in axs.flat:
    ax.set(xlabel="Time [h]", xlim=[0, t.timesteps_used_horizon-1])
plt.grid()
plt.show()

bd = Building(environment=e, objective="none")
bes = BuildingEnergySystem(environment=e)
ap = Apartment(environment=e)
bd. addMultipleEntities(entities=[bes, ap])
bes . addDevice(objectInstance=pv)
ap. addMultipleEntities(entities=[fi, ba])

cd = CityDistrict(environment=e, objective="price")
cd. addEntity(bd, position=(0, 0))

opt = CentralOptimization(city_district=cd, mode="integer")
res = opt.solve()
cd.copy_schedule(dst="optim_schedule")

from pycity_scheduling.util.metric import self_consumption
from pycity_scheduling.util.plot_schedules import plot_entity
from pycity_scheduling.util.write_schedules import schedule_to_json

cd.load_schedule(schedule="optim_schedule")

plot_entity(entity=cd, schedule=["optim_schedule"], title="City district - Cost-optimal schedules")
plot_entity(entity=ba, schedule=["optim_schedule"], title="Battery unit - Cost-optimal schedules")

print(self_consumption(entity=bd))

schedule_to_json(input_list=[fi, pv, ba], file_name="cost_optim.json", schedule=["optim_schedule"])
