import unittest

import numpy as np

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import algorithms


class TestAlgorithms(unittest.TestCase):

    def setUp(self):

        t = Timer(op_horizon=2)
        p = Prices(t)
        w = Weather(t)
        e = Environment(t, w, p)
        cd = CityDistrict(e, objective='peak-shaving')

        bd1 = Building(e, objective='peak-shaving')
        cd.addEntity(bd1, [0, 0])
        bes = BuildingEnergySystem(e)
        bd1.addEntity(bes)
        tes = ThermalEnergyStorage(e, 40, 0.5)
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

        bd2 = Building(e, objective='peak-shaving')
        cd.addEntity(bd2, [0, 0])
        bes = BuildingEnergySystem(e)
        bd2.addEntity(bes)
        tes = ThermalEnergyStorage(e, 40, 0.5)
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

        self.timer = t
        self.cd = cd
        self.bd1 = bd1
        self.bd2 = bd2

    def test_exchange_admm(self):
        f = algorithms['exchange-admm']
        f(self.cd, rho=2, eps_primal=0.001)

        self.assertEqual(20, self.bd1.P_El_Schedule[0])
        self.assertEqual(20, self.bd1.P_El_Schedule[1])
        self.assertEqual(40, self.bd2.P_El_Schedule[0])
        self.assertEqual(40, self.bd2.P_El_Schedule[1])
        self.assertAlmostEqual(60, self.cd.P_El_Schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.P_El_Schedule[1], 2)

    def test_dual_decomposition(self):
        f = algorithms['dual-decomposition']
        f(self.cd, eps_primal=0.001)

        self.assertEqual(20, self.bd1.P_El_Schedule[0])
        self.assertEqual(20, self.bd1.P_El_Schedule[1])
        self.assertEqual(40, self.bd2.P_El_Schedule[0])
        self.assertEqual(40, self.bd2.P_El_Schedule[1])
        self.assertAlmostEqual(60, self.cd.P_El_Schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.P_El_Schedule[1], 2)

    def test_stand_alone_algorithm(self):
        f = algorithms['stand-alone']
        f(self.cd)

        self.assertEqual(20, self.bd1.P_El_Schedule[0])
        self.assertEqual(20, self.bd1.P_El_Schedule[1])
        self.assertEqual(40, self.bd2.P_El_Schedule[0])
        self.assertEqual(40, self.bd2.P_El_Schedule[1])
        self.assertEqual(60, self.cd.P_El_Schedule[0], 2)
        self.assertEqual(60, self.cd.P_El_Schedule[1], 2)

    def test_local_algorithm(self):
        f = algorithms['local']
        f(self.cd)

        self.assertEqual(20, self.bd1.P_El_Schedule[0])
        self.assertEqual(20, self.bd1.P_El_Schedule[1])
        self.assertEqual(40, self.bd2.P_El_Schedule[0])
        self.assertEqual(40, self.bd2.P_El_Schedule[1])
        self.assertEqual(60, self.cd.P_El_Schedule[0], 2)
        self.assertEqual(60, self.cd.P_El_Schedule[1], 2)

    def test_central_algorithm(self):
        f = algorithms['central']
        f(self.cd)

        self.assertEqual(20, self.bd1.P_El_Schedule[0])
        self.assertEqual(20, self.bd1.P_El_Schedule[1])
        self.assertEqual(40, self.bd2.P_El_Schedule[0])
        self.assertEqual(40, self.bd2.P_El_Schedule[1])
        self.assertEqual(60, self.cd.P_El_Schedule[0], 2)
        self.assertEqual(60, self.cd.P_El_Schedule[1], 2)
