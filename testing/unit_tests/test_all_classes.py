import unittest

from pycity_scheduling.classes import *


class TestAllClasses(unittest.TestCase):
    def test_all_classes(self):
        t = Timer()
        p = Prices(t)
        w = Weather(t)
        e = Environment(t, w, p)
        cd = CityDistrict(e)
        bd = Building(e)
        cd.addEntity(bd, [0, 0])
        bes = BuildingEnergySystem(e)
        bd.addEntity(bes)
        tes = ThermalEnergyStorage(e, 1000, 0.5)
        bes.addDevice(tes)
        bat = Battery(e, 10, 10)
        bes.addDevice(bat)
        bl = Boiler(e, 10, 1)
        eh = ElectricalHeater(e, 10)
        hp = HeatPump(e, 10)
        chp = CombinedHeatPower(e, 10, 10, 0.5)
        bes.addMultipleDevices([bl, eh, hp, chp])
        ap = Apartment(e)
        bd.addEntity(ap)
        fl = FixedLoad(e, method=1, annualDemand=6000,
                       profileType='H0')
        sh = SpaceHeating(e, method=1, livingArea=100, specificDemand=50,
                          profile_type='HEF')
        ap.addMultipleEntities([fl, sh])
        ev = ElectricalVehicle(e, 10, 10, 1, [1]*48+[0]*48)
        ap.addEntity(ev)
        cl = CurtailableLoad(e, 0.1, 0.5)
        dl = DeferrableLoad(e, 10, 10, [1]*96)
        ap.addMultipleEntities([cl, dl])
