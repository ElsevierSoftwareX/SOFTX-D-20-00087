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
        self.bat = Battery(e, 10, 20, soc_init=0.875, eta=0.5)

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

    def test_update_schedule(self):
        m1, var_list = get_model(3)
        m1.optimize()
        self.bat.P_El_vars = var_list
        m2, var_list = get_model(3, 2)
        m2.optimize()
        self.bat.E_El_vars = var_list
        a = np.arange(3)

        self.bat.update_schedule()
        self.assertTrue(np.array_equal(a, self.bat.P_El_Schedule))
        self.assertTrue(np.array_equal(a * 2, self.bat.E_El_Schedule))

    def test_populate_deviation_model(self):
        m = gp.Model()
        self.bat.populate_deviation_model(m, 'full')
        m.update()

        c = self.bat.E_El_Act_coupl_constr
        self.assertEqual(-0.125, m.getCoeff(c, self.bat.P_El_Act_Demand_var))
        self.assertEqual(0.5, m.getCoeff(c, self.bat.P_El_Act_Supply_var))
        self.assertEqual(1, m.getCoeff(c, self.bat.E_El_Act_var))

    def test_update_deviation_model(self):
        m = gp.Model()
        self.bat.populate_deviation_model(m)
        self.bat.P_El_Schedule = np.arange(-1, 2) * 4
        self.bat.E_El_Schedule = np.arange(-1, 2)
        self.bat.update_deviation_model(m, 0)
        m.optimize()

        self.assertEqual(0, self.bat.P_El_Act_Demand_var.x)
        self.assertEqual(4, self.bat.P_El_Act_Supply_var.x)

        self.bat.update_deviation_model(m, 2)
        m.optimize()

        self.assertEqual(4, self.bat.P_El_Act_Demand_var.x)
        self.assertEqual(0, self.bat.P_El_Act_Supply_var.x)

        m = gp.Model()
        self.bat.populate_deviation_model(m, 'full')
        self.bat.E_El_Act_Schedule = np.full(3, 9)
        self.bat.update_deviation_model(m, 2, mode='full')
        self.bat.E_El_Act_var.Obj = 100
        self.bat.P_El_Act_Demand_var.Obj = 1
        m.optimize()

        self.assertEqual(0, self.bat.E_El_Act_var.x)
        self.assertEqual(18, self.bat.P_El_Act_Supply_var.x)
        self.assertEqual(9, self.bat.E_El_Act_coupl_constr.RHS)

        self.bat.E_El_Act_var.Obj = -100
        m.optimize()

        self.assertEqual(10, self.bat.E_El_Act_var.x)
        self.assertEqual(8, self.bat.P_El_Act_Demand_var.x)

    def test_calculate_co2(self):
        self.bat.P_El_Schedule = np.array([10]*3)
        self.assertEqual(0, self.bat.calculate_co2())


class TestBoiler(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bl = Boiler(e, 10, 0.4)

    def test_calculate_co2(self):
        self.bl.P_Th_Schedule = - np.array([10] * 8)
        self.bl.P_Th_Ref_Schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = self.bl.calculate_co2(co2_emissions=co2_em)
        self.assertEqual(23750, co2)
        co2 = self.bl.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(11875, co2)
        co2 = self.bl.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(9500, co2)


class TestBuilding(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bd = Building(e)

    def test_get_objective(self):
        m, var_list = get_model(4)
        self.bd.P_El_vars = var_list
        m.optimize()

        self.bd.environment.prices.tou_prices = np.array([1]*2 + [4]*6)
        self.assertAlmostEqual(8.4, self.bd.get_objective().getValue())
        self.bd.environment.prices.co2_prices = np.array([4]*2 + [1]*6)
        self.bd.objective = 'co2'
        self.assertAlmostEqual(3.6, self.bd.get_objective().getValue())
        self.bd.objective = 'peak-shaving'
        self.assertAlmostEqual(14, self.bd.get_objective().getValue())

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
        co2 = self.bd.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(1000, co2)
        co2 = self.bd.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(1100, co2)


class TestCurtailableLoad(unittest.TestCase):
    combinations = [(4, 1), (3, 1), (2, 1), (1, 1), (2, 2), (3, 1),
                    (0, 1), (0, 2), (0, 3), (0, 4)]
    horizon = 5
    def setUp(self):
        self.e = get_env(5, 20)
    def test_populate_model(self):
        model = gp.Model('CLModel')
        cl = CurtailableLoad(self.e, 2, 0.5)
        cl.populate_model(model)
        obj = gp.quicksum(cl.P_El_vars)
        model.setObjective(obj)
        model.optimize()
        cl.update_schedule()
        self.assertAlmostEqual(5, obj.getValue())
        self.assertTrue(
            5, sum(cl.P_El_Schedule[:5]))

    def test_populate_model_on_off(self):
        model = gp.Model('CLModel')
        cl = CurtailableLoad(self.e, 2, 0.5, 2, 2)
        cl.populate_model(model)
        obj = gp.quicksum(cl.P_El_vars)
        model.setObjective(obj)
        model.optimize()
        cl.update_schedule()
        self.assertAlmostEqual(7, obj.getValue())
        self.assertAlmostEqual(7, sum(cl.P_El_Schedule[:5]))

    def test_populate_model_integer(self):
        for low, full in self.combinations:
            min_states = sum(np.tile([False]*low + [True]*full, 5)[:5])
            for nom in [0.5, 1, 2]:
                with self.subTest(msg="max_low={} min_full={} nom={}".format(low, full, nom)):
                    model = gp.Model('CLModel')
                    cl = CurtailableLoad(self.e, nom, 0.75, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = gp.quicksum(cl.P_El_vars)
                    model.setObjective(obj)
                    model.optimize()
                    cl.update_schedule()
                    schedule_states = np.isclose(cl.P_El_Schedule[:5], [nom]*5)
                    self.assertTrue(
                        np.array_equal(schedule_states, cl.P_State_schedule[:5])
                    )
                    self.assertEqual(min_states, sum(schedule_states))
                    self.assertAlmostEqual(min_states*nom+(5-min_states)*nom*0.75, obj.getValue())

    def test_update_model(self):
        for width in [1, 2, 4, 5]:
            with self.subTest(msg="step width={}".format(width)):
                model = gp.Model('CLModel')
                cl = CurtailableLoad(self.e, 2, 0.5)
                cl.populate_model(model)
                obj = gp.quicksum(cl.P_El_vars)
                model.setObjective(obj)
                for t in range(0, 20-5+1, width):
                    self.e.timer.currentTimestep = t
                    cl.upate_model(model)
                    model.optimize()
                    cl.update_schedule()
                    self.assertAlmostEqual(5, obj.getValue())
                    self.assertAlmostEqual(5, sum(cl.P_El_Schedule[t:t+5]))

    def test_update_model_on_off(self):
        for low, full in self.combinations:
            for width in [1, 2, 4, 5]:
                with self.subTest(msg="max_low={} min_full={} step width={}".format(low, full, width)):
                    model = gp.Model('CLModel')
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model)
                    obj = gp.quicksum(cl.P_El_vars)
                    model.setObjective(obj)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.currentTimestep = t
                        cl.upate_model(model)
                        model.optimize()
                        cl.update_schedule()

                    endtimestep = self.e.timer.currentTimestep + cl.op_horizon
                    for t in range(0, endtimestep):
                        self.assertGreaterEqual(cl.P_El_Schedule[t], 1)
                        self.assertLessEqual(cl.P_El_Schedule[t], 2)
                    for t in range(0, endtimestep-(low+full)+1):
                        self.assertGreaterEqual(sum(cl.P_El_Schedule[t:t+low+full]),
                                                1*low + 2*full)

    def test_update_model_integer(self):
        for low, full in self.combinations:
            states = np.tile([False] * low + [True] * full, 20)[:20]
            for width in [1, 2, 4, 5]:
                with self.subTest(msg="max_low={} min_full={} step width={}".format(low, full, width)):
                    model = gp.Model('CLModel')
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = gp.quicksum(cl.P_El_vars)
                    model.setObjective(obj)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.currentTimestep = t
                        cl.upate_model(model)
                        obj = gp.quicksum(cl.P_El_vars)
                        obj += cl.get_objective(coeff_flex=0.2)
                        model.setObjective(obj)
                        for i, var in enumerate(cl.P_State_vars):
                            var.lb = states[t+i]
                            var.ub = states[t+i]
                        model.optimize()
                        self.assertEqual(model.Status, 2)
                        cl.update_schedule()
                        schedule_states_el = np.isclose(cl.P_El_Schedule[t:t+5], [2] * 5)
                        schedule_states_b = np.isclose(cl.P_State_schedule[t:t+5], [1] * 5)
                        self.assertTrue(
                            np.array_equal(schedule_states_el, schedule_states_b)
                        )
                        self.assertTrue(
                            np.array_equal(states[t:t+5], schedule_states_b)
                        )
                        self.assertTrue(np.allclose(
                            cl.P_El_Schedule[t:t+5],
                            np.full(5, 2 * 0.5) + np.array(states[t:t+5]) * (2 * (1. - 0.5))
                        ))


class TestCityDistrict(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.cd = CityDistrict(e)

    def test_get_objective(self):
        m, var_list = get_model(4)
        self.cd.P_El_vars = var_list
        m.optimize()

        self.cd.environment.prices.da_prices = np.array([1]*2 + [4]*6)
        self.assertAlmostEqual(8.4, self.cd.get_objective().getValue())
        self.cd.objective = 'peak-shaving'
        self.assertAlmostEqual(14, self.cd.get_objective().getValue())
        self.cd.objective = 'valley-filling'
        self.cd.valley_profile = np.array([-1]*8)
        self.assertAlmostEqual(2, self.cd.get_objective().getValue())

    def test_calculate_costs(self):
        self.cd.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.cd.P_El_Ref_Schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = self.cd.calculate_costs(prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = self.cd.calculate_costs(timestep=4, prices=prices)
        self.assertEqual(100, costs)
        costs = self.cd.calculate_costs(schedule='ref', prices=prices)
        self.assertEqual(-40, costs)

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
        co2 = self.cd.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(1000, co2)
        co2 = self.cd.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(1100, co2)

    def test_self_consumption(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.P_El_Ref_Schedule = np.array([2]*2 + [-6]*2 + [-9]*2 + [-1]*2)
        pv.P_El_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Ref_Schedule = - np.array([0]*8)

        self.assertEqual(0.25, self.cd.self_consumption())
        self.assertEqual(0.5, self.cd.self_consumption(timestep=4))
        self.assertEqual(1, self.cd.self_consumption(schedule='ref'))

    def test_autarky(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.P_El_Ref_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Ref_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)

        self.assertEqual(0.5, self.cd.autarky())
        self.assertEqual(0, self.cd.autarky(timestep=2))
        self.assertEqual(1, self.cd.autarky(schedule='ref'))


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
        co2 = self.chp.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(11875, co2)
        co2 = self.chp.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(9500, co2)


class TestDeferrableLoad(unittest.TestCase):
    def setUp(self):
        self.e = get_env(6, 9)
        self.lt = [0, 1, 1, 1, 0, 1, 1, 1, 0]

    def test_update_model(self):
        dl = DeferrableLoad(self.e, 19, 10, load_time=self.lt)
        model = gp.Model('DLModel')
        dl.populate_model(model)
        obj = gp.QuadExpr()
        obj.addTerms(
            [1] * 6,
            dl.P_El_vars,
            dl.P_El_vars
        )
        model.setObjective(obj)
        dl.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10 * 4/3, gp.quicksum(dl.P_El_vars).getValue() * dl.time_slot, places=5)

        dl.timer.mpc_update()
        dl.update_model(model)
        model.optimize()

        for t, c in enumerate(self.lt[1:7]):
            if c:
                self.assertEqual(19, dl.P_El_vars[t].ub)
            else:
                self.assertEqual(0, dl.P_El_vars[t].ub)
        self.assertAlmostEqual(13.333333, dl.P_El_vars[4].x, places=5)
        self.assertAlmostEqual(13.333333, dl.P_El_vars[5].x, places=5)

        dl.timer.mpc_update()
        dl.timer.mpc_update()
        dl.P_El_Schedule[1] = 15
        dl.P_El_Schedule[2] = 15
        dl.update_model(model)
        model.optimize()

        self.assertAlmostEqual(10, dl.P_El_vars[0].x, places=5)

    def test_update_model_integer(self):
        dl = DeferrableLoad(self.e, 19, 9.5 - 1e-6, load_time=self.lt)
        model = gp.Model('DLModel')
        dl.populate_model(model, mode="integer")
        obj = gp.QuadExpr()
        obj.addTerms(
            [0] * 2 + [1] * 2 + [0] * 2,
            dl.P_El_vars,
            dl.P_El_vars
        )
        model.setObjective(obj)
        dl.update_model(model, mode="integer")
        model.optimize()
        dl.update_schedule()

        self.assertTrue(np.array_equal(
            dl.P_El_Schedule[:6],
            [0, 19, 19, 0, 0, 19]
        ))
        for _ in range(3):
            dl.timer.mpc_update()
            dl.update_model(model, mode="integer")
            model.optimize()
            dl.update_schedule()

        self.assertTrue(np.array_equal(
            dl.P_El_Schedule,
            [0, 19, 19, 0, 0, 0, 19, 19, 0]
        ))

    def test_update_model_integer_small_horizon(self):
        e = get_env(1, 9)
        dl = DeferrableLoad(e, 19, 9.5, load_time=self.lt)
        model = gp.Model('DLModel')
        dl.populate_model(model, mode="integer")
        for _ in range(8):
            dl.update_model(model, mode="integer")
            model.optimize()
            dl.update_schedule()
            dl.timer.mpc_update()

        self.assertTrue(np.array_equal(
            dl.P_El_Schedule,
            [0, 19, 19, 0, 0, 19, 19, 0, 0]
        ))


class TestFixedLoad(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        load = np.arange(1, 5)
        self.fl = FixedLoad(e, method=0, demand=load)

    def test_update_deviation_model(self):
        m = gp.Model()
        unc = np.full_like(4, 2)
        self.fl.set_new_uncertainty(unc)
        self.fl.populate_deviation_model(m)
        self.fl.update_deviation_model(m, 0)
        m.optimize()

        self.assertEqual(2, self.fl.P_El_Act_var.x)

        self.fl.update_deviation_model(m, 2)
        m.optimize()

        self.assertEqual(6, self.fl.P_El_Act_var.x)


class TestElectricalEntity(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.ee = ElectricalEntity(e)
        self.ee.environment = e

    def test_update_schedule(self):
        m, var_list = get_model(4)
        m.optimize()
        self.ee.P_El_vars = var_list
        a = np.arange(4)

        self.ee.update_schedule()
        self.assertTrue(np.array_equal(a, self.ee.P_El_Schedule[:4]))
        self.ee.timer.mpc_update()
        self.ee.update_schedule()
        self.assertTrue(np.array_equal(a, self.ee.P_El_Schedule[4:]))

    def test_calculate_costs(self):
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.ee.P_El_Act_Schedule = np.array([2]*4 + [-4]*4)
        self.ee.P_El_Ref_Schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = self.ee.calculate_costs(prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = self.ee.calculate_costs(timestep=4, prices=prices)
        self.assertEqual(100, costs)
        costs = self.ee.calculate_costs(schedule='act', prices=prices)
        self.assertEqual(20, costs)
        costs = self.ee.calculate_costs(schedule='ref', prices=prices)
        self.assertEqual(40, costs)

    def test_self_consumption(self):
        # properly tested in CityDistrict
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, self.ee.self_consumption())

    def test_autarky(self):
        # properly tested in CityDistrict
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, self.ee.autarky())


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
        self.assertAlmostEqual(2, self.ev.E_El_vars[3].x, places=5)

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
        self.assertAlmostEqual(2, self.ev.E_El_vars[2].x, places=5)
        self.assertLessEqual(1.6, self.ev.E_El_vars[-1].x)

        self.ev.timer.mpc_update()
        self.ev.timer.mpc_update()
        self.ev.update_model(model)
        model.optimize()

        self.assertAlmostEqual(5, self.ev.E_El_vars[-1].x, places=5)

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


class TestHeatPump(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.hp = HeatPump(e, 10, cop=np.full(8, 11))

    def test_populate_model(self):
        m = gp.Model()
        self.hp.populate_model(m)
        m.update()

        c = self.hp.coupl_constrs[0]
        self.assertEqual(1, m.getCoeff(c, self.hp.P_El_vars[0]))
        self.assertEqual(-1, m.getCoeff(c, self.hp.P_Th_vars[0]))

    def test_update_model(self):
        m = gp.Model()
        self.hp.populate_model(m)
        self.hp.update_model(m)
        m.update()

        c = self.hp.coupl_constrs[0]
        self.assertEqual(11, m.getCoeff(c, self.hp.P_El_vars[0]))

    def test_populate_devitation_model(self):
        m = gp.Model()
        self.hp.populate_deviation_model(m)
        m.update()

        c = self.hp.Act_coupl_constr
        self.assertEqual(1, m.getCoeff(c, self.hp.P_El_Act_var))
        self.assertEqual(1, m.getCoeff(c, self.hp.P_Th_Act_var))

    def test_update_devitation_model(self):
        m = gp.Model()
        self.hp.populate_deviation_model(m)
        self.hp.update_deviation_model(m, 0)
        m.update()

        c = self.hp.Act_coupl_constr
        self.assertEqual(11, m.getCoeff(c, self.hp.P_El_Act_var))


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
        co2 = self.pv.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(750, co2)
        co2 = self.pv.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(600, co2)


class TestPrices(unittest.TestCase):
    def test_cache(self):
        Prices.co2_price_cache = None
        Prices.da_price_cache = None
        Prices.tou_price_cache = None
        ti = Timer(op_horizon=4, mpc_horizon=8, step_size=3600,
                   initial_date=(2015, 1, 1), initial_time=(1, 0, 0))
        pr = Prices(ti)

        self.assertEqual(35040, len(pr.da_price_cache))
        self.assertEqual(35040, len(pr.tou_price_cache))
        self.assertEqual(35040, len(pr.co2_price_cache))
        self.assertTrue(np.allclose(pr.tou_prices, [23.2621]*6 + [42.2947]*2))

        Prices.da_price_cache[4] = 20
        ti = Timer(op_horizon=4, mpc_horizon=8, step_size=900,
                   initial_date=(2015, 1, 1), initial_time=(1, 0, 0))
        pr = Prices(ti)

        self.assertAlmostEqual(20, pr.da_prices[0], places=4)


class TestThermalEnergyStorage(unittest.TestCase):
    def setUp(self):
        e = get_env(3)
        self.tes = ThermalEnergyStorage(e, 40, 0.5)

    def test_update_schedule(self):
        m1, var_list = get_model(3)
        m1.optimize()
        self.tes.P_Th_vars = var_list
        m2, var_list = get_model(3, 2)
        m2.optimize()
        self.tes.E_Th_vars = var_list
        a = np.arange(3)

        self.tes.update_schedule()
        self.assertTrue(np.array_equal(a, self.tes.P_Th_Schedule))
        self.assertTrue(np.array_equal(a * 2, self.tes.E_Th_Schedule))

    def test_populate_deviation_model(self):
        m = gp.Model()
        self.tes.populate_deviation_model(m, 'full')
        m.update()

        c = self.tes.E_Th_Act_coupl_constr
        self.assertEqual(-0.25, m.getCoeff(c, self.tes.P_Th_Act_var))
        self.assertEqual(1, m.getCoeff(c, self.tes.E_Th_Act_var))

    def test_update_deviation_model(self):
        m = gp.Model()
        self.tes.populate_deviation_model(m)
        self.tes.P_Th_Schedule = np.arange(-1, 2) * 4
        self.tes.E_Th_Schedule = np.arange(-1, 2)
        self.tes.update_deviation_model(m, 0)
        m.optimize()

        self.assertEqual(-4, self.tes.P_Th_Act_var.x)

        self.tes.update_deviation_model(m, 2)
        m.optimize()

        self.assertEqual(4, self.tes.P_Th_Act_var.x)

        m = gp.Model()
        self.tes.populate_deviation_model(m, 'full')
        self.tes.E_Th_Act_Schedule = np.full(3, 10)
        self.tes.update_deviation_model(m, 2, mode='full')
        self.tes.E_Th_Act_var.Obj = 1
        m.optimize()

        self.assertEqual(0, self.tes.E_Th_Act_var.x)
        self.assertEqual(-40, self.tes.P_Th_Act_var.x)
        self.assertEqual(10, self.tes.E_Th_Act_coupl_constr.RHS)

        self.tes.E_Th_Act_var.Obj = -1
        m.optimize()

        self.assertEqual(40, self.tes.E_Th_Act_var.x)
        self.assertEqual(120, self.tes.P_Th_Act_var.x)


class TestThermalEntity(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.th = ThermalEntity(e)
        self.th.environment = e

    def test_update_schedule(self):
        m, var_list = get_model(4)
        m.optimize()
        self.th.P_Th_vars = var_list
        a = np.arange(4)

        self.th.update_schedule()
        self.assertTrue(np.array_equal(a, self.th.P_Th_Schedule[:4]))
        self.th.timer.mpc_update()
        self.th.update_schedule()
        self.assertTrue(np.array_equal(a, self.th.P_Th_Schedule[4:]))


class TestSpaceHeating(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        load = np.arange(1, 5)
        self.sh = SpaceHeating(e, method=0, loadcurve=load)

    def test_update_deviation_model(self):
        m = gp.Model()
        unc = np.full_like(4, 2)
        self.sh.set_new_uncertainty(unc)
        self.sh.populate_deviation_model(m)
        self.sh.update_deviation_model(m, 0)
        m.optimize()

        self.assertEqual(2, self.sh.P_Th_Act_var.x)

        self.sh.update_deviation_model(m, 2)
        m.optimize()

        self.assertEqual(6, self.sh.P_Th_Act_var.x)


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
        co2 = self.wec.calculate_co2(timestep=4, co2_emissions=co2_em)
        self.assertEqual(250, co2)
        co2 = self.wec.calculate_co2(schedule='ref', co2_emissions=co2_em)
        self.assertEqual(200, co2)


def get_env(op_horizon, mpc_horizon=None, mpc_step_width=1):
    ti = Timer(op_horizon=op_horizon,
               mpc_horizon=mpc_horizon,
               mpc_step_width=mpc_step_width)
    we = Weather(ti)
    pr = Prices(ti)
    return Environment(ti, we, pr)


def get_model(var_length, factor=1):
    m = gp.Model()
    var_list = []
    for i in range(var_length):
        b = i*factor
        var_list.append(m.addVar(lb=b, ub=b))
    return m, var_list
