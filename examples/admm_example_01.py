import numpy as np

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import algorithms


t = Timer(op_horizon=2)
p = Prices(t)
w = Weather(t)
e = Environment(t, w, p)
cd = CityDistrict(e, objective='valley_filling')

bd1 = Building(e, objective='peak_shaving')
cd.addEntity(bd1, [0, 0])
bes = BuildingEnergySystem(e)
bd1.addEntity(bes)
tes = ThermalEnergyStorage(e, 40, 0.5, 0.5)
bes.addDevice(tes)
eh = ElectricalHeater(e, 10)
bes.addDevice(eh)
ap = Apartment(e)
bd1.addEntity(ap)
load = np.array([10, 10])
fi = FixedLoad(e, method=0, demand=load)
ap.addEntity(fi)
sh = SpaceHeating(e, method=0, loadcurve=load)
ap.addEntity(sh)

bd2 = Building(e, objective='price')
cd.addEntity(bd2, [0, 0])
bes = BuildingEnergySystem(e)
bd2.addEntity(bes)
tes = ThermalEnergyStorage(e, 40, 0.5, 0.5)
bes.addDevice(tes)
eh = ElectricalHeater(e, 20)
bes.addDevice(eh)
ap = Apartment(e)
bd2.addEntity(ap)
load = np.array([20, 20])
fi = FixedLoad(e, method=0, demand=load)
ap.addEntity(fi)
sh = SpaceHeating(e, method=0, loadcurve=load)
ap.addEntity(sh)


f = algorithms['exchange-admm']
r = f(cd, rho=2, eps_primal=0.001)


print(r[0])
print(r[1])
print(r[2])
print(r[3])

