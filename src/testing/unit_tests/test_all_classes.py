"""
#######################################
### The pycity_scheduling framework ###
#######################################


Institution:
############
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
########
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
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
        ths = ThermalHeatingStorage(e, 1000, 0.5)
        bes.addDevice(ths)
        tcs = ThermalCoolingStorage(e, 500, 0.75)
        bes.addDevice(tcs)
        bat = Battery(e, 10, 10)
        bes.addDevice(bat)
        bl = Boiler(e, 10, 1)
        eh = ElectricalHeater(e, 10)
        hp = HeatPump(e, 10)
        chp = CombinedHeatPower(e, 10, 10, 0.5)
        ch = Chiller(e, 12)
        bes.addMultipleDevices([bl, eh, hp, chp, ch])
        ap = Apartment(e)
        bd.addEntity(ap)
        fl = FixedLoad(e, method=1, annual_demand=6000, profile_type='H0')
        sh = SpaceHeating(e, method=1, living_area=100, specific_demand=50, profile_type='HEF')
        sc = SpaceCooling(e, method=0, loadcurve=sh.loadcurve)
        ap.addMultipleEntities([fl, sh, sc])
        ev = ElectricalVehicle(e, 10, 10, soc_init=1, charging_time=[1]*48+[0]*48)
        ap.addEntity(ev)
        cl = CurtailableLoad(e, 0.1, 0.5)
        dl = DeferrableLoad(e, 10, 10, [1]*96)
        ap.addMultipleEntities([cl, dl])
        return
