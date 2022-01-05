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
