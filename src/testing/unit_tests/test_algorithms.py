"""
The pycity_scheduling framework


@institution:
Institute for Automation of Complex Power Systems (ACS)
E.ON Energy Research Center
RWTH Aachen University

@author:
Sebastian Schwarz, M.Sc.
Sebastian Alexander Uerlich, B.Sc.
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import unittest
import pyomo.environ as pyomo

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import algorithms
from pycity_scheduling.exception import *


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
        ths = ThermalHeatingStorage(e, 40, 0.5)
        bes.addDevice(ths)
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
        ths = ThermalHeatingStorage(e, 40, 0.5)
        bes.addDevice(ths)
        eh = ElectricalHeater(e, 20)
        bes.addDevice(eh)
        ap = Apartment(e)
        bd2.addEntity(ap)
        load = np.array([20, 20])
        fi = FixedLoad(e, method=0, demand=load)
        ap.addEntity(fi)
        sh = SpaceHeating(e, method=0, loadcurve=load)
        ap.addEntity(sh)

        wec = WindEnergyConverter(e, [50, 50], [0, 0], force_renewables=False)
        cd.addEntity(wec, [0, 0])

        pv = Photovoltaic(e, method=1, peak_power=4.6, force_renewables=False)
        cd.addEntity(pv, [0, 0])

        self.timer = t
        self.cd = cd
        self.bd1 = bd1
        self.bd2 = bd2
        return

    def test_exchange_admm(self):
        f = algorithms['exchange-admm'](self.cd, rho=2.0, eps_primal=0.001)
        r = f.solve()

        self.assertAlmostEqual(20, self.bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(20, self.bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[0], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[1], 4)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[1], 2)
        self.assertTrue(r["r_norms"][-2] > 0.001 or r["s_norms"][-2] > 1)
        self.assertGreater(0.001, r["r_norms"][-1])
        self.assertGreater(1, r["s_norms"][-1])

        # Test infeasible model:
        self.bd1.model.new_constr = pyomo.Constraint(expr=self.bd1.model.p_el_vars[0] == 0)
        self.bd1.model.p_el_vars[0].setub(15.0)
        with self.assertRaises(NonoptimalError):
            f.solve(full_update=True, debug=False)

        f2 = algorithms['exchange-admm'](self.cd, rho=2, eps_primal=0.001, max_iterations=2)
        with self.assertRaises(MaxIterationError):
            f2.solve()
        return

    def test_exchange_admm_beta(self):
        t = Timer(op_horizon=2)
        p = Prices(t)
        w = Weather(t)
        e = Environment(t, w, p)
        cd = CityDistrict(e, objective='peak-shaving')

        bd1 = Building(e, objective='none')
        cd.addEntity(bd1, [0, 0])
        bes = BuildingEnergySystem(e)
        bd1.addEntity(bes)
        ap = Apartment(e)
        bd1.addEntity(ap)
        load = np.array([10, -10])
        fi = FixedLoad(e, method=0, demand=load)
        ap.addEntity(fi)

        bd2 = Building(e, objective='peak-shaving')
        cd.addEntity(bd2, [0, 0])
        bes = BuildingEnergySystem(e)
        bd2.addEntity(bes)
        bat = Battery(e, 100, 100, storage_end_equality=True)
        bes.addDevice(bat)

        f = algorithms['exchange-admm'](cd, rho=2, eps_primal=0.001, eps_dual=0.01)
        r = f.solve()
        self.assertAlmostEqual(10, bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(-10, bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(-5, bd2.p_el_schedule[0], 2)
        self.assertAlmostEqual(5, bd2.p_el_schedule[1], 2)
        self.assertAlmostEqual(5, cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(-5, cd.p_el_schedule[1], 2)

        r = f.solve(full_update=False, beta=0)
        self.assertAlmostEqual(10, bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(-10, bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(-10, bd2.p_el_schedule[0], 2)
        self.assertAlmostEqual(10, bd2.p_el_schedule[1], 2)
        self.assertAlmostEqual(0, cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(0, cd.p_el_schedule[1], 2)

        r = f.solve(full_update=False, beta={bd1.ID: 0, bd2.ID: 1, cd.ID: 0})
        self.assertAlmostEqual(10, bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(-10, bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(0, bd2.p_el_schedule[0], 2)
        self.assertAlmostEqual(0, bd2.p_el_schedule[1], 2)
        self.assertAlmostEqual(10, cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(-10, cd.p_el_schedule[1], 2)
        return

    def test_dual_decomposition(self):
        f = algorithms['dual-decomposition'](self.cd, eps_primal=0.001)
        f.solve()

        self.assertAlmostEqual(20, self.bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(20, self.bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[0], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[1], 4)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[1], 2)
        return

    def test_stand_alone_algorithm(self):
        f = algorithms['stand-alone'](self.cd)
        f.solve()

        self.assertAlmostEqual(20, self.bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(20, self.bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[0], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[1], 4)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[1], 2)
        return

    def test_local_algorithm(self):
        f = algorithms['local'](self.cd)
        f.solve()

        self.assertAlmostEqual(20, self.bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(20, self.bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[0], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[1], 4)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[1], 2)
        return

    def test_central_algorithm(self):
        f = algorithms['central'](self.cd)
        f.solve()

        self.assertAlmostEqual(20, self.bd1.p_el_schedule[0], 4)
        self.assertAlmostEqual(20, self.bd1.p_el_schedule[1], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[0], 4)
        self.assertAlmostEqual(40, self.bd2.p_el_schedule[1], 4)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[0], 2)
        self.assertAlmostEqual(60, self.cd.p_el_schedule[1], 2)
        return
