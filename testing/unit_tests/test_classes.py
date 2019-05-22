import datetime
import unittest

import numpy as np
from shapely.geometry import Point
import gurobipy as gp

from pycity_scheduling.classes import *


gp.setParam('outputflag', 0)


class TestModule(unittest.TestCase):
    def test_filter_entities(self):
        e = get_env(4, 8)
        bd = Building(e)
        bes = BuildingEnergySystem(e)
        pv = Photovoltaic(e, 0, 0)
        bes.addDevice(pv)
        bd.addEntity(bes)

        def do_test(gen):
            entities = list(gen)
            self.assertEqual(1, len(entities))
            self.assertIn(pv, entities)

        do_test(filter_entities(bd.get_entities(), 'PV'))
        do_test(filter_entities(bd, 'res_devices'))
        do_test(filter_entities(bd, [Photovoltaic]))
        do_test(filter_entities(bd, ['PV']))
        do_test(filter_entities(bd, {'PV': Photovoltaic}))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, 'PPV'))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, [int]))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, None))


class TestBattery(unittest.TestCase):
    def setUp(self):
        e = get_env(3)
        self.bat = Battery(e, 10, 20, SOC_Ini=0.875, eta=0.5)

    def test_populate_model(self):
        model = gp.Model('BatModel')
        self.bat.populate_model(model)
        model.addConstr(self.bat.E_El_vars[2] == 10)
        model.addConstr(self.bat.E_El_vars[0] == 5)
        obj = gp.QuadExpr()
        obj.addTerms(
            [1] * 3,
            self.bat.P_El_Demand_vars,
            self.bat.P_El_Demand_vars
        )
        model.setObjective(obj)
        model.optimize()

        var_list = [var.varname for var in model.getVars()]
        self.assertEqual(12, len(var_list))
        var_sum = sum(map(lambda v: v.x, self.bat.P_El_vars[1:]))
        self.assertAlmostEqual(40, var_sum, places=5)
        var_sum = sum(map(
            lambda v: v.x,
            self.bat.P_El_Supply_vars[1:] + self.bat.P_El_Demand_vars[1:]
        ))
        self.assertAlmostEqual(40, var_sum, places=5)

    def test_update_model(self):
        model = gp.Model('BatModel')
        demand_var = model.addVar()
        self.bat.P_El_Demand_vars.append(demand_var)
        self.bat.P_El_Supply_vars.append(model.addVar())
        self.bat.E_El_vars.append(model.addVar())
        self.bat.update_model(model)
        model.addConstr(self.bat.E_El_vars[0] == 10)
        obj = demand_var * demand_var
        model.setObjective(obj)
        model.optimize()

        self.assertAlmostEqual(10, demand_var.x, places=5)


class TestBuilding(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bd = Building(e)

    def test_calculate_co2(self):
        bes = BuildingEnergySystem(self.bd.environment)
        pv = Photovoltaic(self.bd.environment, 0, 0)
        bes.addDevice(pv)
        self.bd.addEntity(bes)
        self.bd.P_El_Schedule = np.array([-5] * 2 + [5] * 4 + [-5] * 2)
        self.bd.P_El_Ref_Schedule = np.array([-2] * 2 + [2] * 4 + [-2] * 2)
        pv.P_El_Schedule = - np.array([10]*8)
        pv.P_El_Ref_Schedule = - np.array([4]*8)
        co2_em = np.array([100]*4 + [400]*4)

        co2 = self.bd.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(2750, co2)
        co2 = self.bd.calculate_co2(co2_emissions=co2_em, timestep=4)
        self.assertEqual(1000, co2)
        co2 = self.bd.calculate_co2(co2_emissions=co2_em, reference=True)
        self.assertEqual(1100, co2)


class TestCityDistrict(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.cd = CityDistrict(e)

    def test_calculate_co2(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([-5]*2 + [5]*4 + [-5]*2)
        self.cd.P_El_Ref_Schedule = np.array([-2]*2 + [2]*4 + [-2]*2)
        pv.P_El_Schedule = - np.array([10]*8)
        pv.P_El_Ref_Schedule = - np.array([4]*8)
        co2_em = np.array([100]*4 + [400]*4)

        co2 = self.cd.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(2750, co2)
        co2 = self.cd.calculate_co2(co2_emissions=co2_em, timestep=4)
        self.assertEqual(1000, co2)
        co2 = self.cd.calculate_co2(co2_emissions=co2_em, reference=True)
        self.assertEqual(1100, co2)


class TestCombinedHeatPower(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.chp = CombinedHeatPower(e, 10, 10, 0.8)

    def test_calculate_co2(self):
        self.chp.P_Th_Schedule = - np.array([10] * 8)
        self.chp.P_Th_Ref_Schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = self.chp.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(23750, co2)
        co2 = self.chp.calculate_co2(co2_emissions=co2_em, timestep=4)
        self.assertEqual(11875, co2)
        co2 = self.chp.calculate_co2(co2_emissions=co2_em, reference=True)
        self.assertEqual(9500, co2)


class TestDeferrableLoad(unittest.TestCase):
    def setUp(self):
        e = get_env(6, 9)
        self.lt = [0, 1, 1, 1, 0, 1, 1, 1, 0]
        self.dl = DeferrableLoad(e, 19, 10, load_time=self.lt)

    def test_update_model(self):
        model = gp.Model('DLModel')
        self.dl.populate_model(model)
        obj = gp.QuadExpr()
        obj.addTerms(
            [1] * 6,
            self.dl.P_El_vars,
            self.dl.P_El_vars
        )
        model.setObjective(obj)
        self.dl.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10, gp.quicksum(self.dl.P_El_vars), places=5)

        self.dl.timer.mpc_update()
        self.dl.update_model(model)
        model.optimize()

        for t, c in enumerate(self.lt[1:7]):
            if c:
                self.assertEqual(19, self.dl.P_El_vars[t].ub)
            else:
                self.assertEqual(0, self.dl.P_El_vars[t].ub)
        self.assertAlmostEqual(13.333333, self.dl.P_El_vars[4].x, places=5)
        self.assertAlmostEqual(13.333333, self.dl.P_El_vars[5].x, places=5)

        self.dl.timer.mpc_update()
        self.dl.timer.mpc_update()
        self.dl.P_El_Schedule[1] = 15
        self.dl.P_El_Schedule[2] = 15
        self.dl.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10, self.dl.P_El_vars[0].x, places=5)


class TestElectricVehicle(unittest.TestCase):
    def setUp(self):
        e = get_env(6, 9)
        self.ct = [1, 1, 1, 0, 0, 0, 1, 1, 1]
        self.ev = ElectricalVehicle(e, 10, 20, 0.5, charging_time=self.ct)

    def test_populate_model(self):
        model = gp.Model('EVModel')
        self.ev.populate_model(model)
        model.addConstr(self.ev.E_El_vars[2] == 10)
        model.addConstr(self.ev.E_El_vars[0] == 5)
        obj = gp.QuadExpr()
        obj.addTerms(
            [1] * 6,
            self.ev.P_El_Demand_vars,
            self.ev.P_El_Demand_vars
        )
        model.setObjective(obj)
        model.optimize()

        var_list = [var.varname for var in model.getVars()]
        self.assertEqual(30, len(var_list))
        var_sum = sum(map(lambda v: v.x, self.ev.P_El_vars[1:]))
        self.assertAlmostEqual(20, var_sum, places=5)
        var_sum = sum(map(
            lambda v: v.x,
            self.ev.P_El_Supply_vars[1:] + self.ev.P_El_Demand_vars[1:]
        ))
        self.assertAlmostEqual(20, var_sum, places=5)

    def test_update_model(self):
        model = gp.Model('EVModel')
        self.ev.populate_model(model)
        self.ev.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10, self.ev.E_El_vars[2].x, places=5)
        self.assertAlmostEqual(0, self.ev.E_El_vars[3].x, places=5)

        self.ev.timer.mpc_update()
        self.ev.update_model(model)
        model.optimize()

        for t, c in enumerate(self.ct[1:7]):
            if c:
                self.assertEqual(20, self.ev.P_El_Demand_vars[t].ub)
                self.assertEqual(20, self.ev.P_El_Supply_vars[t].ub)
                self.assertEqual(0, self.ev.P_El_Drive_vars[t].ub)
            else:
                self.assertEqual(0, self.ev.P_El_Demand_vars[t].ub)
                self.assertEqual(0, self.ev.P_El_Supply_vars[t].ub)
                self.assertEqual(gp.GRB.INFINITY,
                                 self.ev.P_El_Drive_vars[t].ub)
        self.assertAlmostEqual(10, self.ev.E_El_vars[1].x, places=5)
        self.assertAlmostEqual(0, self.ev.E_El_vars[2].x, places=5)
        self.assertAlmostEqual(3.33333333, self.ev.E_El_vars[-1].x, places=5)

        self.ev.timer.mpc_update()
        self.ev.timer.mpc_update()
        self.ev.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10, self.ev.E_El_vars[-1].x, places=5)

    def test_get_objective(self):
        model = gp.Model('EVModel')
        self.ev.P_El_vars.append(model.addVar())
        self.ev.P_El_vars.append(model.addVar())
        self.ev.P_El_vars.append(model.addVar())
        self.ev.P_El_vars.append(model.addVar())
        self.ev.P_El_vars.append(model.addVar())
        self.ev.P_El_vars.append(model.addVar())
        obj = self.ev.get_objective(11)
        for i in range(6):
            ref = (i + 1) / 21 * 6 * 11
            coeff = obj.getCoeff(i)
            self.assertAlmostEqual(ref, coeff, places=5)


class TestPhotovoltaic(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.pv = Photovoltaic(e, 30, 0.3)

    def test_calculate_co2(self):
        self.pv.P_El_Schedule = - np.array([10]*8)
        self.pv.P_El_Ref_Schedule = - np.array([4]*8)
        co2_em = np.array([1111]*8)

        co2 = self.pv.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(1500, co2)
        co2 = self.pv.calculate_co2(co2_emissions=co2_em, timestep=4)
        self.assertEqual(750, co2)
        co2 = self.pv.calculate_co2(co2_emissions=co2_em, reference=True)
        self.assertEqual(600, co2)


class TestTimer(unittest.TestCase):
    def setUp(self):
        self.timer = Timer(mpc_horizon=192, mpc_step_width=4,
                           initial_date=(2015, 1, 15), initial_time=(12, 0, 0))
        self.timer._dt = datetime.datetime(2015, 1, 15, 13)

    def test_time_in_year(self):
        self.assertEqual(1396, self.timer.time_in_year())
        self.assertEqual(1392, self.timer.time_in_year(from_init=True))

    def test_time_in_week(self):
        self.assertEqual(340, self.timer.time_in_week())
        self.assertEqual(336, self.timer.time_in_week(from_init=True))

    def test_time_in_day(self):
        self.assertEqual(52, self.timer.time_in_day())
        self.assertEqual(48, self.timer.time_in_day(from_init=True))


class TestWindEnergyConverter(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.wec = WindEnergyConverter(e, [0, 10], [0, 10])

    def test_calculate_co2(self):
        self.wec.P_El_Schedule = - np.array([10] * 8)
        self.wec.P_El_Ref_Schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = self.wec.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(500, co2)
        co2 = self.wec.calculate_co2(co2_emissions=co2_em, timestep=4)
        self.assertEqual(250, co2)
        co2 = self.wec.calculate_co2(co2_emissions=co2_em, reference=True)
        self.assertEqual(200, co2)


def get_env(op_horizon, mpc_horizon=None):
    ti = Timer(op_horizon=op_horizon,
               mpc_horizon=mpc_horizon,
               mpc_step_width=1)
    we = Weather(ti)
    pr = Prices(ti)
    return Environment(ti, we, pr)
