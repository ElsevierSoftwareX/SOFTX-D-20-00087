import datetime
import unittest
import logging

import numpy as np
import pyomo.environ as pyomo
from pyomo.opt import SolverStatus, TerminationCondition
from shapely.geometry import Point

from pycity_scheduling.classes import *
from pycity_scheduling.util.metric import *


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
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        model.c1 = pyomo.Constraint(expr=self.bat.model.E_El_vars[2] == 10)
        model.c2 = pyomo.Constraint(expr=self.bat.model.E_El_vars[0] == 5)
        obj = pyomo.sum_product(self.bat.model.P_El_Demand_vars, self.bat.model.P_El_Demand_vars)
        model.o = pyomo.Objective(expr=obj)
        result = solve_model(model)

        # TODO stats are currently not currect due to a pyomo bug
        # use result as a workaround
        #model.compute_statistics()
        #stats = model.statistics
        #self.assertEqual(12, stats.number_of_variables)
        self.assertEqual(14, result.Problem[0].number_of_variables)
        var_sum = pyomo.value(pyomo.quicksum(self.bat.model.P_El_vars[t] for t in range(1, 3)))
        self.assertAlmostEqual(40, var_sum, places=5)
        var_sum = pyomo.value(pyomo.quicksum(
            self.bat.model.P_El_Supply_vars[t] + self.bat.model.P_El_Demand_vars[t] for t in range(1, 3)
        ))
        self.assertAlmostEqual(40, var_sum, places=5)

    def test_update_model(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        demand_var = self.bat.model.P_El_vars
        self.bat.update_model()
        model.c1 = pyomo.Constraint(expr=self.bat.model.E_El_vars[0] == 10)
        obj = pyomo.sum_product(demand_var, demand_var)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)

        self.assertAlmostEqual(10, pyomo.value(demand_var[0]), places=5)

    def test_update_schedule(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        self.bat.update_model()
        self.bat.model.P_El_Demand_vars.setlb(3)
        self.bat.model.P_El_Demand_vars.setub(3)
        self.bat.model.P_El_Supply_vars.setlb(0)
        self.bat.model.P_El_Supply_vars.setub(0)
        obj = pyomo.sum_product(self.bat.model.P_El_Demand_vars, self.bat.model.P_El_Demand_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        self.bat.update_schedule()
        assert_equal_array(self.bat.P_El_Schedule, [3] * 3)
        assert_equal_array(self.bat.E_El_Schedule, 0.875 * 10 + np.arange(1, 4)*3*0.25*0.5)


    def test_calculate_co2(self):
        self.bat.P_El_Schedule = np.array([10]*3)
        self.assertEqual(0, calculate_co2(self.bat))

    def test_get_objective(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        obj = self.bat.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        for t in range(3):
            self.assertIn(self.bat.model.P_El_vars[t], vs)
            self.bat.model.P_El_vars[t] = t * 5
        self.assertEqual(3, len(vs))
        self.assertEqual(sum(2*(5*t)**2 for t in range(3)), pyomo.value(obj))


class TestBoiler(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bl = Boiler(e, 10, 0.4)

    def test_calculate_co2(self):
        self.bl.P_Th_Schedule = - np.array([10] * 8)
        self.bl.P_Th_Ref_Schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.bl, co2_emissions=co2_em)
        self.assertEqual(23750, co2)
        co2 = calculate_co2(self.bl, timestep=4, co2_emissions=co2_em)
        self.assertEqual(11875, co2)
        self.bl.load_schedule("Ref")
        co2 = calculate_co2(self.bl, co2_emissions=co2_em)
        self.assertEqual(9500, co2)

    def test_lower_activation(self):
        e = get_env(4, 8)
        bl = Boiler(e, 10, lower_activation_limit=0.5)
        model = pyomo.ConcreteModel()
        bl.populate_model(model, "integer")
        bl.update_model("integer")
        model.o = pyomo.Objective(expr=bl.model.P_Th_vars[0])
        results = solve_model(model)
        self.assertEqual(TerminationCondition.optimal, results.solver.termination_condition)
        bl.model.P_Th_vars[0].setub(-0.1)
        bl.model.P_Th_vars[0].setlb(-4.9)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(TerminationCondition.infeasible, results.solver.termination_condition)


class TestBuilding(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bd = Building(e)

    def test_get_objective(self):
        m = pyomo.ConcreteModel()
        self.bd.populate_model(m)
        self.bd.update_model()
        solve_model(m)

        self.bd.environment.prices.tou_prices = np.array([1]*2 + [4]*6)
        self.assertAlmostEqual(8.4, pyomo.value(self.bd.get_objective()))
        self.bd.environment.prices.co2_prices = np.array([4]*2 + [1]*6)
        self.bd.objective = 'co2'
        self.assertAlmostEqual(3.6, pyomo.value(self.bd.get_objective()))
        self.bd.objective = 'peak-shaving'
        self.assertAlmostEqual(14, pyomo.value(self.bd.get_objective()))

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

        co2 = calculate_co2(self.bd, co2_emissions=co2_em)
        self.assertEqual(2750, co2)
        co2 = calculate_co2(self.bd, timestep=4, co2_emissions=co2_em)
        self.assertEqual(1000, co2)
        self.bd.load_schedule("Ref")
        co2 = calculate_co2(self.bd, co2_emissions=co2_em)
        self.assertEqual(1100, co2)

    def test_get_objective(self):
        model = pyomo.ConcreteModel()
        env = self.bd.environment
        env.prices.tou_prices[:4] = [1, 2, 3, 4]
        env.prices.co2_prices[:4] = [5, 4, 3, 2]
        bes = BuildingEnergySystem(env)
        self.bd.addEntity(bes)
        self.bd.populate_model(model)
        obj = self.bd.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(4, len(vs))
        for t in range(4):
            self.bd.model.P_El_vars[t].value = 10**t
        self.assertAlmostEqual(2*4321/10*4, pyomo.value(obj), places=5)

        model = pyomo.ConcreteModel()
        bd2 = Building(env, 'co2')
        bd2.addEntity(bes)
        bd2.populate_model(model)
        obj = bd2.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(4, len(vs))
        for t in range(4):
            bd2.model.P_El_vars[t].value = 10**t
        # rounding errors caused by /14 and co2_prices being np.float32
        self.assertAlmostEqual(2*2345/14*4, pyomo.value(obj), places=3)

        model = pyomo.ConcreteModel()
        bd3 = Building(env, 'peak-shaving')
        bd3.addEntity(bes)
        bd3.populate_model(model)
        obj = bd3.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(4, len(vs))
        for t in range(4):
            bd3.model.P_El_vars[t].value = 10**t
        self.assertEqual(2*1010101, pyomo.value(obj))

        model = pyomo.ConcreteModel()
        bd4 = Building(env, None)
        bd4.addEntity(bes)
        bd4.populate_model(model)
        obj = bd4.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(0, len(vs))
        for t in range(4):
            bd4.model.P_El_vars[t].value = 10 ** t
        self.assertEqual(0, pyomo.value(obj))

        bd5 = Building(env, "invalid")
        self.assertRaisesRegex(ValueError, ".*Building.*", bd5.get_objective)

    def testReset(self):
        env = self.bd.environment
        bes = BuildingEnergySystem(env)
        self.bd.addEntity(bes)
        schedules = list(self.bd.schedules.keys())
        model = pyomo.ConcreteModel()
        self.bd.populate_model(model)
        self.bd.update_model()
        model.o = pyomo.Objective(expr=pyomo.sum_product(self.bd.model.P_El_vars))
        solve_model(model)
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        self.bd.update_schedule()
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        self.bd.schedules["Ref"]["P_El"] = np.arange(8)
        self.bd.copy_schedule("new", "Ref")
        schedules.append("new")
        self.bd.reset("Ref")
        for k in schedules:
            if k == "new":
                e = np.arange(8)
            else:
                e = np.zeros(8)
            assert_equal_array(self.bd.schedules[k]["P_El"], e)
        self.bd.reset()
        for k in schedules:
            assert_equal_array(self.bd.schedules[k]["P_El"], np.zeros(8))
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        with self.assertRaises(KeyError):
            self.bd.load_schedule("nonexistent")
            self.bd.P_El_Schedule
        with self.assertRaises(KeyError):
            self.bd.load_schedule(None)
            self.bd.P_El_Schedule


class TestCurtailableLoad(unittest.TestCase):
    combinations = [(4, 1), (3, 1), (2, 1), (1, 1),
                    (1, 3), (1, 4), (2, 2), (2, 3),
                    (0, 1), (0, 2), (0, 3), (0, 4)]
    horizon = 5
    def setUp(self):
        self.e = get_env(5, 20)
    def test_populate_model(self):
        model = pyomo.ConcreteModel()
        cl = CurtailableLoad(self.e, 2, 0.5)
        cl.populate_model(model)
        obj = pyomo.sum_product(cl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        cl.update_schedule()
        self.assertAlmostEqual(5, pyomo.value(obj))
        self.assertTrue(
            5, sum(cl.P_El_Schedule[:5]))

    def test_populate_model_on_off(self):
        model = pyomo.ConcreteModel()
        cl = CurtailableLoad(self.e, 2, 0.5, 2, 2)
        cl.populate_model(model)
        obj = pyomo.sum_product(cl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        cl.update_schedule()
        self.assertAlmostEqual(7, pyomo.value(obj))
        self.assertAlmostEqual(7, sum(cl.P_El_Schedule[:5]))

    def test_populate_model_integer(self):
        for low, full in self.combinations:
            min_states = sum(np.tile([False]*low + [True]*full, 5)[:5])
            for nom in [0.5, 1, 2]:
                with self.subTest(msg="max_low={} min_full={} nom={}".format(low, full, nom)):
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, nom, 0.75, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = pyomo.sum_product(cl.model.P_El_vars)
                    model.o = pyomo.Objective(expr=obj)
                    results = solve_model(model)
                    cl.update_schedule()
                    schedule_states = np.isclose(cl.P_El_Schedule[:5], [nom]*5)
                    assert_equal_array(cl.P_State_Schedule[:5], schedule_states)
                    self.assertEqual(min_states, sum(schedule_states))
                    self.assertAlmostEqual(min_states*nom+(5-min_states)*nom*0.75, pyomo.value(obj))

    def test_update_model(self):
        for width in [1, 2, 4, 5]:
            with self.subTest(msg="step width={}".format(width)):
                model = pyomo.ConcreteModel()
                cl = CurtailableLoad(self.e, 2, 0.5)
                cl.populate_model(model)
                obj = pyomo.sum_product(cl.model.P_El_vars)
                model.o = pyomo.Objective(expr=obj)
                solve_model(model)
                for t in range(0, 20-5+1, width):
                    self.e.timer.currentTimestep = t
                    cl.update_model()
                    solve_model(model)
                    cl.update_schedule()
                    self.assertAlmostEqual(5, pyomo.value(obj))
                    self.assertAlmostEqual(5, sum(cl.P_El_Schedule[t:t+5]))

    def test_update_model_on_off(self):
        for low, full in self.combinations:
            for width in [1, 2, 4, 5]:
                with self.subTest(msg="max_low={} min_full={} step width={}".format(low, full, width)):
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model)
                    obj = pyomo.sum_product(cl.model.P_El_vars)
                    model.o = pyomo.Objective(expr=obj)
                    solve_model(model)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.currentTimestep = t
                        cl.update_model()
                        solve_model(model)
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
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = pyomo.sum_product(cl.model.P_El_vars)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.currentTimestep = t
                        cl.update_model(mode="integer")
                        model.o = pyomo.Objective(expr=obj)
                        results = solve_model(model)
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                        best_obj = pyomo.value(obj)
                        model.o_constr = pyomo.Constraint(expr=best_obj == obj)
                        model.del_component("o")
                        model.o = pyomo.Objective(expr=pyomo.sum_product(range(0, -cl.op_horizon, -1),
                                                                         cl.model.P_El_vars))
                        results = solve_model(model)
                        model.del_component("o")
                        model.del_component("o_constr")
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                        cl.update_schedule()
                        schedule_states_el = np.isclose(cl.P_El_Schedule[t:t+5], [2] * 5)
                        schedule_states_b = np.isclose(cl.P_State_Schedule[t:t+5], [1] * 5)
                        assert_equal_array(schedule_states_b, states[t:t + 5])
                        assert_equal_array(schedule_states_el, schedule_states_b)
                        assert_equal_array(
                            cl.P_El_Schedule[t:t+5],
                            np.full(5, 2 * 0.5) + np.array(states[t:t+5]) * (2 * (1. - 0.5))
                        )

    def test_integer_first(self):
        for low, full in self.combinations:
            if low > 0:
                with self.subTest(msg="max_low={} min_full={}".format(low, full)):
                    model = pyomo.ConcreteModel()

                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model, mode="integer")
                    self.e.timer.currentTimestep = 1
                    cl.P_State_Schedule[0] = False
                    cl.P_El_Schedule[0] = 1
                    cl.update_model("integer")

                    cl.model.P_State_vars[0].setub(1)
                    cl.model.P_State_vars[0].setlb(1)
                    cl.model.P_State_vars[1].setub(0)
                    cl.model.P_State_vars[1].setlb(0)

                    model.o = pyomo.Objective(expr=cl.model.P_State_vars[0])
                    logger = logging.getLogger("pyomo.core")
                    oldlevel = logger.level
                    logger.setLevel(logging.ERROR)
                    results = solve_model(model)
                    logger.setLevel(oldlevel)
                    if full > 1:
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)
                    else:
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)

    def test_small_horizon(self):
        for width in [1, 2, 4]:
            for horizon in [1, 2, 4]:
                if horizon >= width:
                    with self.subTest(msg="width={} horizon={}".format(width, horizon)):
                        e = get_env(horizon, 20)
                        model = pyomo.ConcreteModel()
                        cl = CurtailableLoad(e, 2, 0.5)
                        cl.populate_model(model)
                        obj = pyomo.sum_product(cl.model.P_El_vars)
                        model.o = pyomo.Objective(expr=obj)
                        for t in range(0, 21 - horizon, width):
                            e.timer.currentTimestep = t
                            cl.update_model()
                            solve_model(model)
                            self.assertEqual(1, pyomo.value(cl.model.P_El_vars[0]))
                            cl.update_schedule()
                        assert_equal_array(cl.P_El_Schedule, [1] * 20)

    def test_small_horizon_low_full(self):
        for horizon in [1, 2, 4]:
            e = get_env(horizon, 20)
            for width in [1, 2, 4]:
                if horizon >= width:
                    for low, full in self.combinations:
                        with self.subTest(msg="width={} horizon={} max_low={} min_full={}"
                                              .format(width, horizon, low, full)):

                            model = pyomo.ConcreteModel()
                            cl = CurtailableLoad(e, 2, 0.5, low, full)
                            cl.populate_model(model)
                            obj = pyomo.sum_product(cl.model.P_El_vars)
                            model.c = pyomo.Objective(expr=obj)
                            for t in range(0, 21 - horizon, width):
                                e.timer.currentTimestep = t
                                cl.update_model()
                                solve_model(model)
                                cl.update_schedule()

                            for t in range(0, 20 - (low + full) + 1):
                                self.assertGreaterEqual(sum(cl.P_El_Schedule[t:t + low + full]),
                                                        1 * low + 2 * full,
                                                        np.array2string(cl.P_El_Schedule))

    def test_small_horizon_low_full_integer(self):
        for horizon in [1, 2, 4]:
            e = get_env(horizon, 20)
            for width in [1, 2, 4]:
                if horizon >= width:
                    for low, full in self.combinations:
                        with self.subTest(msg="width={} horizon={} max_low={} min_full={}".format(width, horizon, low, full)):
                            states = np.tile([1] * low + [2] * full, 20)[:20]
                            model = pyomo.ConcreteModel()
                            cl = CurtailableLoad(e, 2, 0.5, low, full)
                            cl.populate_model(model, mode="integer")
                            obj = pyomo.sum_product(cl.model.P_El_vars)
                            for t in range(0, 21 - horizon, width):
                                e.timer.currentTimestep = t
                                cl.update_model(mode="integer")
                                model.o = pyomo.Objective(expr=obj)
                                results = solve_model(model)
                                self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                                best_obj = pyomo.value(obj)
                                model.o_constr = pyomo.Constraint(expr=best_obj == obj)
                                model.del_component("o")
                                model.o = pyomo.Objective(expr=pyomo.sum_product(range(-1, -cl.op_horizon-1, -1),
                                                                                 cl.model.P_El_vars))
                                results = solve_model(model)
                                model.del_component("o")
                                model.del_component("o_constr")
                                self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                                cl.update_schedule()

                            assert_equal_array(cl.P_El_Schedule, states)


class TestCityDistrict(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.cd = CityDistrict(e)

    def test_get_objective(self):
        m = pyomo.ConcreteModel()
        self.cd.populate_model(m)
        def zero_constr(model, t):
            return model.P_El_vars[t] == 0
        self.cd.model.extra_constr = pyomo.Constraint(self.cd.model.t, rule=zero_constr)
        m.o = pyomo.Objective(expr=self.cd.get_objective())
        solve_model(m)

        for t in range(4):
            self.cd.model.P_El_vars[t].value = t

        self.assertEqual(self.cd.objective, "price")
        self.cd.environment.prices.da_prices = np.array([1]*2 + [4]*6)
        self.assertAlmostEqual(8.4, pyomo.value(self.cd.get_objective()))
        self.cd.objective = 'peak-shaving'
        self.assertAlmostEqual(14, pyomo.value(self.cd.get_objective()))
        self.cd.objective = 'valley-filling'
        self.cd.valley_profile = np.array([-1]*8)
        self.assertAlmostEqual(2, pyomo.value(self.cd.get_objective()))
        self.cd.objective = None
        self.assertAlmostEqual(0, pyomo.value(self.cd.get_objective()))
        self.cd.objective = "invalid"
        self.assertRaisesRegex(ValueError, ".*CityDistrict.*", self.cd.get_objective)

        m = pyomo.ConcreteModel()
        self.cd.objective = "max-consumption"
        self.cd.populate_model(m)
        self.cd.model.P_El_vars[0].setub(-1)
        m.o = pyomo.Objective(expr=self.cd.get_objective())
        solve_model(m)
        self.assertAlmostEqual(1, pyomo.value(self.cd.get_objective()))


    def test_calculate_costs(self):
        self.cd.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.cd.P_El_Ref_Schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = calculate_costs(self.cd, prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = calculate_costs(self.cd, timestep=4, prices=prices)
        self.assertEqual(100, costs)
        self.cd.load_schedule("Ref")
        costs = calculate_costs(self.cd, prices=prices)
        self.assertEqual(-40, costs)

    def test_calculate_co2(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([-5]*2 + [5]*4 + [-5]*2)
        self.cd.P_El_Ref_Schedule = np.array([-2]*2 + [2]*4 + [-2]*2)
        pv.P_El_Schedule = - np.array([10]*8)
        pv.P_El_Ref_Schedule = - np.array([4]*8)
        co2_em = np.array([100]*4 + [400]*4)

        co2 = calculate_co2(self.cd, co2_emissions=co2_em)
        self.assertEqual(2750, co2)
        co2 = calculate_co2(self.cd, timestep=4, co2_emissions=co2_em)
        self.assertEqual(1000, co2)
        self.cd.load_schedule("Ref")
        co2 = calculate_co2(self.cd, co2_emissions=co2_em)
        self.assertEqual(1100, co2)

    def test_self_consumption(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.P_El_Ref_Schedule = np.array([2]*2 + [-6]*2 + [-9]*2 + [-1]*2)
        pv.P_El_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Ref_Schedule = - np.array([0]*8)

        self.assertEqual(0.25, self_consumption(self.cd))
        self.assertEqual(0.5, self_consumption(self.cd, timestep=4))
        self.cd.load_schedule("Ref")
        self.assertEqual(1, self_consumption(self.cd))

    def test_calculate_adj_costs(self):
        self.cd.P_El_Schedule = np.array([4] * 2 + [-4] * 2 + [-10] * 2 + [-2] * 2)
        self.cd.P_El_Ref_Schedule = np.array([2] * 2 + [-6] * 2 + [-9] * 2 + [-1] * 2)
        prices = np.array([10] * 4 + [20] * 4)
        costs_adj = calculate_adj_costs(self.cd, "Ref", prices=prices)
        self.assertEqual(2*5+2*5+1*10+1*10, costs_adj)
        costs_adj = calculate_adj_costs(self.cd, "Ref", prices=prices, total_adjustments=False)
        self.assertEqual(20, costs_adj)
        self.cd.copy_schedule("Ref")
        costs_adj = calculate_adj_costs(self.cd, "Ref", prices=prices)
        self.assertEqual(0, costs_adj)

    def test_autarky(self):
        pv = Photovoltaic(self.cd.environment, 0, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.P_El_Schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.P_El_Ref_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.P_El_Ref_Schedule = - np.array([0]*2 + [8]*4 + [0]*2)

        self.assertEqual(0.5, autarky(self.cd))
        self.assertEqual(0, autarky(self.cd, timestep=2))
        self.cd.load_schedule("Ref")
        self.assertEqual(1, autarky(self.cd))


class TestCombinedHeatPower(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.chp = CombinedHeatPower(e, 10, 10, 0.8)

    def test_calculate_co2(self):
        self.chp.P_Th_Schedule = - np.array([10] * 8)
        self.chp.P_Th_Ref_Schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.chp, co2_emissions=co2_em)
        self.assertEqual(23750, co2)
        co2 = calculate_co2(self.chp, timestep=4, co2_emissions=co2_em)
        self.assertEqual(11875, co2)
        self.chp.load_schedule("Ref")
        co2 = calculate_co2(self.chp, co2_emissions=co2_em)
        self.assertEqual(9500, co2)

    def test_lower_activation(self):
        e = get_env(4, 8)
        chp = CombinedHeatPower(e, 10, 10, 0.8, 0.5)
        m = pyomo.ConcreteModel()
        chp.populate_model(m, "integer")
        chp.update_model("integer")
        obj = pyomo.sum_product(chp.model.P_El_vars, chp.model.P_El_vars)
        obj += 2*3 * pyomo.sum_product(chp.model.P_El_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        chp.update_schedule()
        assert_equal_array(chp.P_El_Schedule[:4], [-5]*4)


class TestDeferrableLoad(unittest.TestCase):
    def setUp(self):
        self.e = get_env(6, 9)
        self.lt = [0, 1, 1, 1, 0, 1, 1, 1, 0]

    def test_update_model(self):
        dl = DeferrableLoad(self.e, 19, 10, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model)
        obj = pyomo.sum_product(dl.model.P_El_vars, dl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        dl.update_model()
        solve_model(model)

        self.assertAlmostEqual(10, pyomo.value(pyomo.sum_product(dl.model.P_El_vars)) * dl.time_slot, places=5)

        dl.timer.mpc_update()
        dl.update_model()
        solve_model(model)

        for t, c in enumerate(self.lt[1:7]):
            if c == 1:
                self.assertEqual(19, dl.model.P_El_vars[t].ub)
            else:
                self.assertEqual(0, dl.model.P_El_vars[t].ub)
        dl.update_schedule()
        assert_equal_array(dl.P_El_Schedule[:7], [0, 8, 8, 8, 0, 8, 8])

    def test_infeasible_consumption(self):
        feasible = DeferrableLoad(self.e, 10, 10, load_time=self.lt)
        m = pyomo.ConcreteModel()
        feasible.populate_model(m)
        feasible.update_model()
        obj = pyomo.sum_product(feasible.model.P_El_vars)
        m.o = pyomo.Objective(expr=obj)
        results = solve_model(m)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)

        m = pyomo.ConcreteModel()
        infeasible = DeferrableLoad(self.e, 10, 10.6, load_time=self.lt)
        infeasible.populate_model(m)
        infeasible.update_model()
        obj = pyomo.sum_product(infeasible.model.P_El_vars)
        m.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(m)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)

    def test_update_model_integer(self):
        dl = DeferrableLoad(self.e, 19, 9.5, load_time=self.lt)
        m = pyomo.ConcreteModel()
        dl.populate_model(m, mode="integer")

        obj = pyomo.sum_product([0] * 2 + [1] * 2 + [0] * 2, dl.model.P_El_vars, dl.model.P_El_vars)
        m.o = pyomo.Objective(expr=obj)
        dl.update_model(mode="integer")
        results = solve_model(m)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
        dl.update_schedule()

        assert_equal_array(dl.P_El_Schedule[:6], [0, 19, 19, 0, 0, 0])
        for _ in range(3):
            dl.timer.mpc_update()
            dl.update_model(mode="integer")
            results = solve_model(m)
            self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
            dl.update_schedule()

        assert_equal_array(dl.P_El_Schedule, [0, 19, 19, 0, 0, 0, 19, 19, 0])

    def test_infeasible_integer(self):
        e = get_env(1, 9)
        dl = DeferrableLoad(e, 19, 9.5, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model, mode="integer")
        dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)

        dl = DeferrableLoad(self.e, 19, 19, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model, mode="integer")
        dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)

        dl = DeferrableLoad(self.e, 19, 19*3/4, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model, mode="integer")
        dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.P_El_vars)
        model.o = pyomo.Objective(expr=obj)
        results = solve_model(model)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
        dl.update_schedule()
        assert_equal_array(dl.P_El_Schedule[:6], [0, 19, 19, 19, 0, 0])


class TestFixedLoad(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        load = np.arange(1, 5)
        model = pyomo.ConcreteModel()
        self.fl = FixedLoad(e, method=0, demand=load)
        self.fl.populate_model(model)
        self.fl.populate_model(model)
        model.o = pyomo.Objective(expr=pyomo.sum_product(self.fl.model.P_El_vars))
        solve_model(model)
        for t in range(2):
            self.assertEqual(self.fl.model.P_El_vars[t].value, load[t])


class TestElectricalEntity(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.ee = ElectricalEntity(e)
        self.ee.environment = e

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.ee.populate_model(m)
        for t in range(4):
            self.ee.model.P_El_vars[t].value = t
        a = np.arange(4)

        self.ee.update_schedule()
        assert_equal_array(self.ee.P_El_Schedule[:4], a)
        self.ee.timer.mpc_update()
        self.ee.update_schedule()
        assert_equal_array(self.ee.P_El_Schedule[4:], a)

    def test_calculate_costs(self):
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.ee.P_El_Ref_Schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = calculate_costs(self.ee, prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = calculate_costs(self.ee, timestep=4, prices=prices)
        self.assertEqual(100, costs)
        self.ee.load_schedule("Ref")
        costs = calculate_costs(self.ee, prices=prices)
        self.assertEqual(40, costs)

    def test_calculate_adj_costs(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        prices = np.array([10] * 4 + [20] * 4)
        costs_adj = calculate_adj_costs(self.ee, "Ref", prices=prices)
        self.assertEqual(6*10 + 16*20, costs_adj)
        costs_adj = calculate_adj_costs(self.ee, "Ref", prices=prices, total_adjustments=False)
        self.assertEqual(16 * 20, costs_adj)
        self.ee.copy_schedule("Ref")
        costs_adj = calculate_adj_costs(self.ee, "Ref", prices=prices)
        self.assertEqual(0, costs_adj)

    def test_calculate_adj_power(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        adj_power = calculate_adj_power(self.ee, "Ref")
        assert_equal_array(adj_power, [6] * 4 + [16] * 4)
        adj_power = calculate_adj_power(self.ee, "Ref", total_adjustments=False)
        assert_equal_array(adj_power, [0] * 4 + [16] * 4)
        adj_power = calculate_adj_power(self.ee, "default")
        assert_equal_array(adj_power, [0] * 8)
        self.ee.load_schedule("Ref")
        adj_power = calculate_adj_power(self.ee, "Ref")
        assert_equal_array(adj_power, [0] * 8)
        self.ee.copy_schedule("default")
        adj_power = calculate_adj_power(self.ee, "default")
        assert_equal_array(adj_power, [0] * 8)

    def test_calculate_adj_energy(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        adj_energy = calculate_adj_energy(self.ee, "Ref")
        self.assertEqual(6 + 16, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "Ref", total_adjustments=False)
        self.assertEqual(16, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "default")
        self.assertEqual(0, adj_energy)
        self.ee.copy_schedule(src="Ref")
        adj_energy = calculate_adj_energy(self.ee, "Ref")
        self.assertEqual(0, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "Ref", total_adjustments=False)
        self.assertEqual(0, adj_energy)
        self.ee.load_schedule("Ref")
        adj_energy = calculate_adj_energy(self.ee, "Ref")
        self.assertEqual(0, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "default")
        self.assertEqual(0, adj_energy)

    def test_metric_delta_g(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        g = metric_delta_g(self.ee, "Ref")
        self.assertEqual(1-30/8, g)
        g = metric_delta_g(self.ee, "default")
        self.assertEqual(0, g)

    def test_peak_to_average_ratio(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        ratio = peak_to_average_ratio(self.ee)
        self.assertEqual(20/5, ratio)
        self.ee.load_schedule("Ref")
        ratio = peak_to_average_ratio(self.ee)
        self.assertEqual(np.inf, ratio)

    def test_peak_reduction_ratio(self):
        self.ee.P_El_Schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.P_El_Ref_Schedule = np.array([4] * 4 + [-4] * 4)
        ratio = peak_reduction_ratio(self.ee, "Ref")
        self.assertEqual((20-4)/4, ratio)
        self.ee.P_El_Ref_Schedule = np.array([4] * 8)
        ratio = peak_reduction_ratio(self.ee, "Ref")
        self.assertEqual((20-4)/4, ratio)
        ratio = peak_reduction_ratio(self.ee, "default")
        self.assertEqual(0, ratio)
        self.ee.load_schedule("Ref")
        ratio = peak_reduction_ratio(self.ee, "Ref")
        self.assertEqual(0, ratio)

    def test_self_consumption(self):
        # properly tested in CityDistrict
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, self_consumption(self.ee))

    def test_autarky(self):
        # properly tested in CityDistrict
        self.ee.P_El_Schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, autarky(self.ee))


class TestElectricalHeater(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.eh = ElectricalHeater(e, 10, 10, 0.8)

    def test_lower_activation(self):
        e = get_env(4, 8)
        eh = ElectricalHeater(e, 10, lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        eh.populate_model(m, "integer")
        eh.update_model("integer")
        obj = pyomo.sum_product(eh.model.P_El_vars, eh.model.P_El_vars)
        obj += -2 * 3 * pyomo.sum_product(eh.model.P_El_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        eh.update_schedule()
        assert_equal_array(eh.P_El_Schedule[:4], [5] * 4)


class TestElectricVehicle(unittest.TestCase):
    def setUp(self):
        e = get_env(6, 9)
        self.ct = [1, 1, 1, 0, 0, 0, 1, 1, 1]
        self.ev = ElectricalVehicle(e, 10, 20, 0.5, charging_time=self.ct)

    def test_populate_model(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        model.c1 = pyomo.Constraint(expr=self.ev.model.E_El_vars[2] == 10)
        model.c2 = pyomo.Constraint(expr=self.ev.model.E_El_vars[0] == 5)
        obj = pyomo.sum_product(self.ev.model.P_El_Demand_vars, self.ev.model.P_El_Demand_vars)
        model.o = pyomo.Objective(expr=obj)
        result = solve_model(model)

        # TODO stats are currently not correct due to a pyomo bug
        # use result as a workaround
        # model.compute_statistics()
        # stats = model.statistics
        # self.assertEqual(30, stats.number_of_variables)
        self.assertEqual(32, result.Problem[0].number_of_variables)
        var_sum = pyomo.value(pyomo.quicksum(self.ev.model.P_El_vars[t] for t in range(1, 6)))
        self.assertAlmostEqual(20, var_sum, places=5)
        var_sum = pyomo.value(pyomo.quicksum(
            self.ev.model.P_El_Supply_vars[t] + self.ev.model.P_El_Demand_vars[t] for t in range(1, 6)))
        self.assertAlmostEqual(20, var_sum, places=5)

    def test_update_model(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        self.ev.update_model()
        model.o = pyomo.Objective(expr=self.ev.get_objective())
        solve_model(model)

        self.assertAlmostEqual(10, self.ev.model.E_El_vars[2].value, places=5)
        self.assertAlmostEqual(2, self.ev.model.E_El_vars[3].value, places=5)

        self.ev.timer.mpc_update()
        self.ev.update_model()
        solve_model(model)

        for t, c in enumerate(self.ct[1:7]):
            if c:
                self.assertEqual(20, self.ev.model.P_El_Demand_vars[t].ub)
                self.assertEqual(20, self.ev.model.P_El_Supply_vars[t].ub)
                self.assertEqual(0, self.ev.model.P_El_Drive_vars[t].ub)
            else:
                self.assertEqual(0, self.ev.model.P_El_Demand_vars[t].ub)
                self.assertEqual(0, self.ev.model.P_El_Supply_vars[t].ub)
                self.assertIsNone(self.ev.model.P_El_Drive_vars[t].ub)
        self.assertAlmostEqual(10, self.ev.model.E_El_vars[1].value, places=5)
        self.assertAlmostEqual(2, self.ev.model.E_El_vars[2].value, places=5)
        self.assertLessEqual(1.6, self.ev.model.E_El_vars[5].value)

        self.ev.timer.mpc_update()
        self.ev.timer.mpc_update()
        self.ev.update_model()
        solve_model(model)

        self.assertAlmostEqual(5, self.ev.model.E_El_vars[5].value, places=5)

    def test_get_objective(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        self.ev.update_model()

        obj = self.ev.get_objective(11)
        for i in range(6):
            ref = (i + 1) / 21 * 6 * 11
            coeff = obj.args[i].args[0].args[0]
            self.assertAlmostEqual(ref, coeff, places=5)


class TestHeatPump(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.hp = HeatPump(e, 10, cop=np.full(8, 11))

    def test_update_model(self):
        m = pyomo.ConcreteModel()
        self.hp.populate_model(m)
        self.hp.update_model()

        c = self.hp.model.p_coupl_constr[0]
        f, l = pyomo.current.decompose_term(c.body)
        self.assertTrue(f)
        for coeff, value in l:
            if value is self.hp.model.P_El_vars[0]:
                self.assertEqual(11, coeff)
            if value is self.hp.model.P_Th_vars[0]:
                self.assertEqual(1, coeff)
            if value is None:
                self.assertEqual(0, coeff)

    def test_lower_activation(self):
        e = get_env(4, 8)
        hp = HeatPump(e, 10, lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        hp.populate_model(m, "integer")
        hp.update_model("integer")
        obj = pyomo.sum_product(hp.model.P_Th_vars, hp.model.P_Th_vars)
        obj += 2 * 3 * pyomo.sum_product(hp.model.P_Th_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        hp.update_schedule()
        assert_equal_array(hp.P_Th_Schedule[:4], [-5] * 4)


class TestPhotovoltaic(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.pv = Photovoltaic(e, 30, 0.3)

    def test_calculate_co2(self):
        self.pv.P_El_Schedule = - np.array([10]*8)
        self.pv.P_El_Ref_Schedule = - np.array([4]*8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.pv, co2_emissions=co2_em)
        self.assertEqual(1500, co2)
        co2 = calculate_co2(self.pv, timestep=4, co2_emissions=co2_em)
        self.assertEqual(750, co2)
        self.pv.load_schedule("Ref")
        co2 = calculate_co2(self.pv, co2_emissions=co2_em)
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
        m = pyomo.ConcreteModel()
        self.tes.populate_model(m)
        self.tes.update_model()
        for t in range(3):
            self.tes.model.P_Th_vars[t].setub(t)
            self.tes.model.P_Th_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.tes.model.P_Th_vars))
        solve_model(m)
        a = np.arange(3)

        self.tes.update_schedule()
        assert_equal_array(self.tes.P_Th_Schedule, a)
        assert_equal_array(self.tes.E_Th_Schedule, [20, 20.25, 20.75])


class TestThermalEntity(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.th = ThermalEntity(e)
        self.th.environment = e

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.th.populate_model(m)
        self.th.update_model()
        for t in range(4):
            self.th.model.P_Th_vars[t].setub(t)
            self.th.model.P_Th_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.th.model.P_Th_vars))
        solve_model(m)
        a = np.arange(4)

        self.th.update_schedule()
        assert_equal_array(self.th.P_Th_Schedule[:4], a)
        self.th.timer.mpc_update()
        self.th.update_schedule()
        assert_equal_array(self.th.P_Th_Schedule[4:], a)


class TestSpaceHeating(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        load = np.arange(1, 5)
        self.sh = SpaceHeating(e, method=0, loadcurve=load)


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

        co2 = calculate_co2(self.wec, co2_emissions=co2_em)
        self.assertEqual(500, co2)
        co2 = calculate_co2(self.wec, timestep=4, co2_emissions=co2_em)
        self.assertEqual(250, co2)
        self.wec.load_schedule("Ref")
        co2 = calculate_co2(self.wec, co2_emissions=co2_em)
        self.assertEqual(200, co2)


def get_env(op_horizon, mpc_horizon=None, mpc_step_width=1):
    ti = Timer(op_horizon=op_horizon,
               mpc_horizon=mpc_horizon,
               mpc_step_width=mpc_step_width)
    we = Weather(ti)
    pr = Prices(ti)
    return Environment(ti, we, pr)


def assert_equal_array(a: np.ndarray, expected):
    if not np.allclose(a, expected):
        expected = np.array(expected)
        msg = "Array {} does not equal expected array {}".format(np.array2string(a), np.array2string(expected))
        raise AssertionError(msg)


def solve_model(model):
    # hack to suppress pyomo no constraint warning
    if not hasattr(model, "simple_var"):
        model.simple_var = pyomo.Var(domain=pyomo.Reals, bounds=(None, None), initialize=0)
        model.simple_constr = pyomo.Constraint(expr=model.simple_var == 1)
    opt = pyomo.SolverFactory('gurobi')
    return opt.solve(model)
