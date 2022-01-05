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
import datetime
import logging
import warnings
import pyomo.environ as pyomo
from pyomo.opt import TerminationCondition
from shapely.geometry import Point

from pycity_scheduling import constants, solvers
from pycity_scheduling.classes import *
from pycity_scheduling.util.metric import *


class TestModule(unittest.TestCase):
    def test_filter_entities(self):
        e = get_env(4, 8)
        bd = Building(e)
        bes = BuildingEnergySystem(e)
        pv = Photovoltaic(e, 0)
        bes.addDevice(pv)
        bd.addEntity(bes)

        def do_test(gen):
            entities = list(gen)
            self.assertEqual(1, len(entities))
            self.assertIn(pv, entities)

        do_test(filter_entities(bd.get_entities(), 'PV'))
        do_test(filter_entities(bd, 'generation_devices'))
        do_test(filter_entities(bd, [Photovoltaic]))
        do_test(filter_entities(bd, ['PV']))
        do_test(filter_entities(bd, {'PV': Photovoltaic}))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, 'PPV'))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, [int]))
        with self.assertRaises(ValueError):
            next(filter_entities(bd, None))
        return


class TestBattery(unittest.TestCase):
    def setUp(self):
        e = get_env(3)
        self.bat = Battery(e, 10, 20, soc_init=0.875, eta=0.5)
        return

    def test_populate_model(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        model.c1 = pyomo.Constraint(expr=self.bat.model.e_el_vars[2] == 10)
        model.c2 = pyomo.Constraint(expr=self.bat.model.e_el_vars[0] == 5)
        obj = pyomo.sum_product(self.bat.model.p_el_demand_vars, self.bat.model.p_el_demand_vars)
        model.o = pyomo.Objective(expr=obj)
        result = solve_model(model)

        # TODO stats are currently not correct due to a pyomo bug
        # use result as a workaround
        #model.compute_statistics()
        #stats = model.statistics
        #self.assertEqual(12, stats.number_of_variables)
        self.assertEqual(13, result.Problem[0].number_of_variables)
        var_sum = pyomo.value(pyomo.quicksum(self.bat.model.p_el_vars[t] for t in range(1, 3)))
        self.assertAlmostEqual(40, var_sum, places=5)
        var_sum = pyomo.value(pyomo.quicksum(
            self.bat.model.p_el_supply_vars[t] + self.bat.model.p_el_demand_vars[t] for t in range(1, 3)
        ))
        self.assertAlmostEqual(40, var_sum, places=5)
        return

    def test_update_model(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        demand_var = self.bat.model.p_el_vars
        self.bat.update_model()
        model.c1 = pyomo.Constraint(expr=self.bat.model.e_el_vars[0] == 10)
        obj = pyomo.sum_product(demand_var, demand_var)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)

        self.assertAlmostEqual(10, pyomo.value(demand_var[0]), places=5)
        return

    def test_update_schedule(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        self.bat.update_model()
        self.bat.model.p_el_demand_vars.setlb(3.0)
        self.bat.model.p_el_demand_vars.setub(3.0)
        self.bat.model.p_el_supply_vars.setlb(0.0)
        self.bat.model.p_el_supply_vars.setub(0.0)
        obj = pyomo.sum_product(self.bat.model.p_el_demand_vars, self.bat.model.p_el_demand_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        self.bat.update_schedule()
        assert_equal_array(self.bat.p_el_schedule, [3] * 3)
        assert_equal_array(self.bat.e_el_schedule, 0.875 * 10 + np.arange(1, 4)*3*0.25*0.5)
        return

    def test_calculate_co2(self):
        self.bat.p_el_schedule = np.array([10]*3)
        self.assertEqual(0, calculate_co2(self.bat))
        return

    def test_get_objective(self):
        model = pyomo.ConcreteModel()
        self.bat.populate_model(model)
        obj = self.bat.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        for t in range(3):
            self.assertIn(self.bat.model.p_el_vars[t], vs)
            self.bat.model.p_el_vars[t] = t * 5
        self.assertEqual(3, len(vs))
        self.assertEqual(sum(2*(5*t)**2 for t in range(3)), pyomo.value(obj))
        return

    def test_e_ini(self):
        expected_schedule = list(range(4, 21, 2))
        e = get_env(3, 9, 2)
        model = pyomo.ConcreteModel()
        bat = Battery(e, 20, 10, soc_init=0.1, eta=0.8)
        bat.populate_model(model)
        model.o = pyomo.Objective(expr=-bat.model.e_el_vars[2])
        for t in range(4):
            bat.update_model()
            solve_model(model)
            bat.update_schedule()
            e.timer.mpc_update()
            assert_equal_array(bat.e_el_schedule, expected_schedule[:3+t*2] + [0] * 2 * (3-t))
            assert_equal_array(bat.p_el_schedule, [10] * (3 + t * 2) + [0] * 2 * (3 - t))
            assert_equal_array(bat.p_el_demand_schedule, [10] * (3 + t * 2) + [0] * 2 * (3 - t))
            assert_equal_array(bat.p_el_supply_schedule, [0] * 9)
        return

    def test_no_discharge(self):
        e = get_env(9, 9)
        model = pyomo.ConcreteModel()
        bat = Battery(e, 30, 10, p_el_max_discharge=0, soc_init=0.5, eta=1)
        bat.populate_model(model)
        bat.update_model()
        model.o = pyomo.Objective(expr=pyomo.sum_product(bat.model.p_el_vars))
        solve_model(model)
        bat.update_schedule()
        assert_equal_array(bat.e_el_schedule, [15] * 9)
        assert_equal_array(bat.p_el_schedule, [0] * 9)
        assert_equal_array(bat.p_el_demand_schedule, [0] * 9)
        assert_equal_array(bat.p_el_supply_schedule, [0] * 9)
        return


class TestBoiler(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bl = Boiler(e, 10, 0.4)
        return

    def test_calculate_co2(self):
        self.bl.p_th_heat_schedule = - np.array([10] * 8)
        self.bl.p_th_heat_ref_schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.bl, co2_emissions=co2_em)
        self.assertEqual(50.0*constants.CO2_EMISSIONS_GAS, co2)
        co2 = calculate_co2(self.bl, timestep=4, co2_emissions=co2_em)
        self.assertEqual(25.0*constants.CO2_EMISSIONS_GAS, co2)
        self.bl.load_schedule("ref")
        co2 = calculate_co2(self.bl, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_GAS, co2)
        return

    def test_lower_activation(self):
        e = get_env(4, 8)
        bl = Boiler(e, 10, lower_activation_limit=0.5)
        model = pyomo.ConcreteModel()
        bl.populate_model(model, "integer")
        bl.update_model("integer")
        model.o = pyomo.Objective(expr=bl.model.p_th_heat_vars[0])
        results = solve_model(model)
        self.assertEqual(TerminationCondition.optimal, results.solver.termination_condition)
        bl.model.p_th_heat_vars[0].setub(-0.1)
        bl.model.p_th_heat_vars[0].setlb(-4.9)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(TerminationCondition.infeasible, results.solver.termination_condition)
        return

    def test_objective(self):
        model = pyomo.ConcreteModel()
        self.bl.populate_model(model)
        self.bl.get_objective()
        return


class TestBuilding(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.bd = Building(e)
        return

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
            self.bd.model.p_el_vars[t].value = 10**t
        self.assertAlmostEqual(2*4321/10*4, pyomo.value(obj), places=5)

        model = pyomo.ConcreteModel()
        bd2 = Building(env, 'co2')
        bd2.addEntity(bes)
        bd2.populate_model(model)
        obj = bd2.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(4, len(vs))
        for t in range(4):
            bd2.model.p_el_vars[t].value = 10**t
        # numerical errors caused by /14 and co2_prices being np.float32
        self.assertAlmostEqual(2*2345/14*4, pyomo.value(obj), places=3)

        model = pyomo.ConcreteModel()
        bd3 = Building(env, 'peak-shaving')
        bd3.addEntity(bes)
        bd3.populate_model(model)
        obj = bd3.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(4, len(vs))
        for t in range(4):
            bd3.model.p_el_vars[t].value = 10**t
        self.assertEqual(2*1010101, pyomo.value(obj))

        model = pyomo.ConcreteModel()
        bd4 = Building(env, None)
        bd4.addEntity(bes)
        bd4.populate_model(model)
        obj = bd4.get_objective(2)
        vs = list(pyomo.current.identify_variables(obj))
        self.assertEqual(0, len(vs))
        for t in range(4):
            bd4.model.p_el_vars[t].value = 10 ** t
        self.assertEqual(0, pyomo.value(obj))

        bd5 = Building(env, "invalid")
        self.assertRaisesRegex(ValueError, ".*Building.*", bd5.get_objective)
        return

    def test_calculate_co2(self):
        bes = BuildingEnergySystem(self.bd.environment)
        pv = Photovoltaic(self.bd.environment, 0)
        bes.addDevice(pv)
        self.bd.addEntity(bes)
        self.bd.p_el_schedule = np.array([-5] * 2 + [5] * 4 + [-5] * 2)
        self.bd.p_el_ref_schedule = np.array([-2] * 2 + [2] * 4 + [-2] * 2)
        pv.p_el_schedule = - np.array([10]*8)
        pv.p_el_ref_schedule = - np.array([4]*8)
        co2_em = np.array([100]*4 + [400]*4)

        co2 = calculate_co2(self.bd, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_PV+1250.0, co2)
        co2 = calculate_co2(self.bd, timestep=4, co2_emissions=co2_em)
        self.assertEqual(10.0*constants.CO2_EMISSIONS_PV+250.0, co2)
        self.bd.load_schedule("ref")
        co2 = calculate_co2(self.bd, co2_emissions=co2_em)
        self.assertEqual(8.0*constants.CO2_EMISSIONS_PV+500.0, co2)
        return

    def test_robustness(self):
        model = pyomo.ConcreteModel()
        env = self.bd.environment
        bes = BuildingEnergySystem(env)
        self.bd.addEntity(bes)
        ths1 = ThermalHeatingStorage(env, 10)
        bes.addDevice(ths1)
        ths2 = ThermalHeatingStorage(env, 25)
        bes.addDevice(ths2)

        ap = Apartment(env)
        self.bd.addEntity(ap)
        loadcurve = np.array([15, 15, 10, 10])
        sh = SpaceHeating(env, loadcurve=loadcurve)
        ap.addEntity(sh)

        eh = ElectricalHeater(env, 20)
        bes.addDevice(eh)

        self.bd.populate_model(model, robustness=(3, 0.5))
        self.bd.update_model(robustness=(3, 0.5))
        assert_equal_array(np.array([self.bd.model.lower_robustness_bounds[i].value for i in range(3)]),
                           np.cumsum(loadcurve[:3])*0.5/4)
        assert_equal_array(np.array([self.bd.model.upper_robustness_bounds[i].value for i in range(3)]),
                           35 - np.cumsum(loadcurve[:3]) * 0.5 / 4)

        self.assertEqual(17.5, self.bd.model.lower_robustness_bounds[3].value)
        self.assertEqual(17.5, self.bd.model.upper_robustness_bounds[3].value)
        return

    def testReset(self):
        env = self.bd.environment
        bes = BuildingEnergySystem(env)
        self.bd.addEntity(bes)
        schedules = list(self.bd.schedules.keys())
        model = pyomo.ConcreteModel()
        self.bd.populate_model(model)
        self.bd.update_model()
        model.o = pyomo.Objective(expr=pyomo.sum_product(self.bd.model.p_el_vars))
        solve_model(model)
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        self.bd.update_schedule()
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        self.bd.schedules["ref"]["p_el"] = np.arange(8)
        self.bd.copy_schedule("new", "ref")
        schedules.append("new")
        self.bd.reset("ref")
        for k in schedules:
            if k == "new":
                e = np.arange(8)
            else:
                e = np.zeros(8)
            assert_equal_array(self.bd.schedules[k]["p_el"], e)
        self.bd.reset()
        for k in schedules:
            assert_equal_array(self.bd.schedules[k]["p_el"], np.zeros(8))
        self.assertEqual(schedules, list(self.bd.schedules.keys()))
        with self.assertRaises(KeyError):
            self.bd.load_schedule("nonexistent")
            self.bd.p_el_schedule
        with self.assertRaises(KeyError):
            self.bd.load_schedule(None)
            self.bd.p_el_schedule
        return


class TestChiller(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.ch = Chiller(e, 10, cop=np.full(8, 11))
        return

    def test_update_model(self):
        m = pyomo.ConcreteModel()
        self.ch.populate_model(m)
        self.ch.update_model()

        c = self.ch.model.p_coupl_constr[0]
        f, l = pyomo.current.decompose_term(c.body)
        self.assertTrue(f)
        for coeff, value in l:
            if value is self.ch.model.p_el_vars[0]:
                self.assertEqual(11, coeff)
            if value is self.ch.model.p_th_cool_vars[0]:
                self.assertEqual(1, coeff)
            if value is None:
                self.assertEqual(0, coeff)
        return

    def test_lower_activation(self):
        e = get_env(4, 8)
        ch = Chiller(e, 10, cop=np.full(8, 11), lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        ch.populate_model(m, "integer")
        ch.update_model("integer")
        obj = pyomo.sum_product(ch.model.p_th_cool_vars, ch.model.p_th_cool_vars)
        obj += 2 * 3 * pyomo.sum_product(ch.model.p_th_cool_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        ch.update_schedule()
        assert_equal_array(ch.p_th_cool_schedule[:4], [-5] * 4)
        return


class TestCurtailableLoad(unittest.TestCase):
    combinations = [(4, 1), (3, 1), (2, 1), (1, 1),
                    (1, 3), (1, 4), (2, 2), (2, 3),
                    (0, 1), (0, 2), (0, 3), (0, 4)]
    horizon = 5

    def setUp(self):
        self.e = get_env(5, 20)
        return

    def test_populate_model(self):
        model = pyomo.ConcreteModel()
        cl = CurtailableLoad(self.e, 2, 0.5)
        cl.populate_model(model)
        obj = pyomo.sum_product(cl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        cl.update_schedule()
        self.assertAlmostEqual(5, pyomo.value(obj))
        self.assertTrue(5, sum(cl.p_el_schedule[:5]))
        return

    def test_populate_model_on_off(self):
        model = pyomo.ConcreteModel()
        cl = CurtailableLoad(self.e, 2, 0.5, 2, 2)
        cl.populate_model(model)
        obj = pyomo.sum_product(cl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        cl.update_schedule()
        self.assertAlmostEqual(7, pyomo.value(obj))
        self.assertAlmostEqual(7, sum(cl.p_el_schedule[:5]))
        return

    def test_populate_model_integer(self):
        for low, full in self.combinations:
            min_states = sum(np.tile([False]*low + [True]*full, 5)[:5])
            for nom in [0.5, 1, 2]:
                with self.subTest(msg="max_low={} min_full={} nom={}".format(low, full, nom)):
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, nom, 0.75, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = pyomo.sum_product(cl.model.p_el_vars)
                    model.o = pyomo.Objective(expr=obj)
                    results = solve_model(model)
                    cl.update_schedule()
                    schedule_states = np.isclose(cl.p_el_schedule[:5], [nom]*5)
                    assert_equal_array(cl.p_state_schedule[:5], schedule_states)
                    self.assertEqual(min_states, sum(schedule_states))
                    self.assertAlmostEqual(min_states*nom+(5-min_states)*nom*0.75, pyomo.value(obj))
        return

    def test_update_model(self):
        for width in [1, 2, 4, 5]:
            with self.subTest(msg="step width={}".format(width)):
                model = pyomo.ConcreteModel()
                cl = CurtailableLoad(self.e, 2, 0.5)
                cl.populate_model(model)
                obj = pyomo.sum_product(cl.model.p_el_vars)
                model.o = pyomo.Objective(expr=obj)
                solve_model(model)
                for t in range(0, 20-5+1, width):
                    self.e.timer.current_timestep = t
                    cl.update_model()
                    solve_model(model)
                    cl.update_schedule()
                    self.assertAlmostEqual(5, pyomo.value(obj))
                    self.assertAlmostEqual(5, sum(cl.p_el_schedule[t:t+5]))
        return

    def test_update_model_on_off(self):
        for low, full in self.combinations:
            for width in [1, 2, 4, 5]:
                with self.subTest(msg="max_low={} min_full={} step width={}".format(low, full, width)):
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model)
                    obj = pyomo.sum_product(cl.model.p_el_vars)
                    model.o = pyomo.Objective(expr=obj)
                    solve_model(model)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.current_timestep = t
                        cl.update_model()
                        solve_model(model)
                        cl.update_schedule()

                    endtimestep = self.e.timer.current_timestep + cl.op_horizon
                    for t in range(0, endtimestep):
                        self.assertGreaterEqual(cl.p_el_schedule[t], 1)
                        self.assertLessEqual(cl.p_el_schedule[t], 2)
                    for t in range(0, endtimestep-(low+full)+1):
                        self.assertGreaterEqual(sum(cl.p_el_schedule[t:t+low+full]) + 1e-4, 1*low + 2*full)
        return

    def test_update_model_integer(self):
        for low, full in self.combinations:
            states = np.tile([False] * low + [True] * full, 20)[:20]
            for width in [1, 2, 4, 5]:
                with self.subTest(msg="max_low={} min_full={} step width={}".format(low, full, width)):
                    model = pyomo.ConcreteModel()
                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model, mode="integer")
                    obj = pyomo.sum_product(cl.model.p_el_vars)
                    for t in range(0, 20-5+1, width):
                        self.e.timer.current_timestep = t
                        cl.update_model(mode="integer")
                        model.o = pyomo.Objective(expr=obj)
                        results = solve_model(model)
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                        best_obj = pyomo.value(obj)
                        model.o_constr = pyomo.Constraint(expr=best_obj == obj)
                        model.del_component("o")
                        model.o = pyomo.Objective(expr=pyomo.sum_product(range(0, -cl.op_horizon, -1),
                                                                         cl.model.p_el_vars))
                        results = solve_model(model)
                        model.del_component("o")
                        model.del_component("o_constr")
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                        cl.update_schedule()
                        schedule_states_el = np.isclose(cl.p_el_schedule[t:t+5], [2] * 5)
                        schedule_states_b = np.isclose(cl.p_state_schedule[t:t+5], [1] * 5)
                        assert_equal_array(schedule_states_b, states[t:t + 5])
                        assert_equal_array(schedule_states_el, schedule_states_b)
                        assert_equal_array(
                            cl.p_el_schedule[t:t+5],
                            np.full(5, 2 * 0.5) + np.array(states[t:t+5]) * (2 * (1. - 0.5))
                        )
        return

    def test_integer_first(self):
        for low, full in self.combinations:
            if low > 0:
                with self.subTest(msg="max_low={} min_full={}".format(low, full)):
                    model = pyomo.ConcreteModel()

                    cl = CurtailableLoad(self.e, 2, 0.5, low, full)
                    cl.populate_model(model, mode="integer")
                    self.e.timer.current_timestep = 1
                    cl.p_state_schedule[0] = False
                    cl.p_el_schedule[0] = 1
                    cl.update_model("integer")

                    cl.model.p_state_vars[0].setub(1.0)
                    cl.model.p_state_vars[0].setlb(1.0)
                    cl.model.p_state_vars[1].setub(0.0)
                    cl.model.p_state_vars[1].setlb(0.0)

                    model.o = pyomo.Objective(expr=cl.model.p_state_vars[0])
                    logger = logging.getLogger("pyomo.core")
                    oldlevel = logger.level
                    logger.setLevel(logging.ERROR)
                    results = solve_model(model)
                    logger.setLevel(oldlevel)
                    if full > 1:
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)
                    else:
                        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
        return

    def test_small_horizon(self):
        for width in [1, 2, 4]:
            for horizon in [1, 2, 4]:
                if horizon >= width:
                    with self.subTest(msg="width={} horizon={}".format(width, horizon)):
                        e = get_env(horizon, 20)
                        model = pyomo.ConcreteModel()
                        cl = CurtailableLoad(e, 2, 0.5)
                        cl.populate_model(model)
                        obj = pyomo.sum_product(cl.model.p_el_vars)
                        model.o = pyomo.Objective(expr=obj)
                        for t in range(0, 21 - horizon, width):
                            e.timer.current_timestep = t
                            cl.update_model()
                            solve_model(model)
                            self.assertEqual(1, pyomo.value(cl.model.p_el_vars[0]))
                            cl.update_schedule()
                        assert_equal_array(cl.p_el_schedule, [1] * 20)
        return

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
                            obj = pyomo.sum_product(cl.model.p_el_vars)
                            model.c = pyomo.Objective(expr=obj)
                            for t in range(0, 21 - horizon, width):
                                e.timer.current_timestep = t
                                cl.update_model()
                                solve_model(model)
                                cl.update_schedule()

                            for t in range(0, 20 - (low + full) + 1):
                                self.assertGreaterEqual(sum(cl.p_el_schedule[t:t + low + full]) + 1e-4,
                                                        1 * low + 2 * full,
                                                        np.array2string(cl.p_el_schedule))
        return

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
                            obj = pyomo.sum_product(cl.model.p_el_vars)
                            for t in range(0, 21 - horizon, width):
                                e.timer.current_timestep = t
                                cl.update_model(mode="integer")
                                model.o = pyomo.Objective(expr=obj)
                                results = solve_model(model)
                                self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                                best_obj = pyomo.value(obj)
                                model.o_constr = pyomo.Constraint(expr=best_obj == obj)
                                model.del_component("o")
                                model.o = pyomo.Objective(expr=pyomo.sum_product(range(-1, -cl.op_horizon-1, -1),
                                                                                 cl.model.p_el_vars))
                                results = solve_model(model)
                                model.del_component("o")
                                model.del_component("o_constr")
                                self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
                                cl.update_schedule()

                            assert_equal_array(cl.p_el_schedule, states)
        return


class TestCityDistrict(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.cd = CityDistrict(e)
        return

    def test_get_objective(self):
        m = pyomo.ConcreteModel()
        self.cd.populate_model(m)

        def zero_constr(model, t):
            return model.p_el_vars[t] == 0

        self.cd.model.extra_constr = pyomo.Constraint(self.cd.model.t, rule=zero_constr)
        m.o = pyomo.Objective(expr=self.cd.get_objective())
        solve_model(m)

        for t in range(4):
            self.cd.model.p_el_vars[t].value = t

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
        self.cd.model.p_el_vars[0].setub(-1)
        m.o = pyomo.Objective(expr=self.cd.get_objective())
        solve_model(m)
        self.assertAlmostEqual(1, pyomo.value(self.cd.get_objective()))
        return

    def test_calculate_costs(self):
        self.cd.p_el_schedule = np.array([10]*4 + [-20]*4)
        self.cd.p_el_ref_schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = calculate_costs(self.cd, prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = calculate_costs(self.cd, timestep=4, prices=prices)
        self.assertEqual(100, costs)
        self.cd.load_schedule("ref")
        costs = calculate_costs(self.cd, prices=prices)
        self.assertEqual(-40, costs)
        return

    def test_calculate_co2(self):
        pv = Photovoltaic(self.cd.environment, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.p_el_schedule = np.array([-5] * 2 + [5] * 4 + [-5] * 2)
        self.cd.p_el_ref_schedule = np.array([-2] * 2 + [2] * 4 + [-2] * 2)
        pv.p_el_schedule = - np.array([10] * 8)
        pv.p_el_ref_schedule = - np.array([4] * 8)
        co2_em = np.array([100] * 4 + [400] * 4)

        co2 = calculate_co2(self.cd, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_PV+1250.0, co2)
        co2 = calculate_co2(self.cd, timestep=4, co2_emissions=co2_em)
        self.assertEqual(10.0*constants.CO2_EMISSIONS_PV+250.0, co2)
        self.cd.load_schedule("ref")
        co2 = calculate_co2(self.cd, co2_emissions=co2_em)
        self.assertEqual(8.0*constants.CO2_EMISSIONS_PV+500.0, co2)
        return

    def test_self_consumption(self):
        pv = Photovoltaic(self.cd.environment, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.p_el_schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.p_el_ref_schedule = np.array([2]*2 + [-6]*2 + [-9]*2 + [-1]*2)
        pv.p_el_schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.p_el_ref_schedule = - np.array([0]*8)

        self.assertEqual(0.25, self_consumption(self.cd))
        self.assertEqual(0.5, self_consumption(self.cd, timestep=4))
        self.cd.load_schedule("ref")
        self.assertEqual(1, self_consumption(self.cd))
        return

    def test_calculate_adj_costs(self):
        self.cd.p_el_schedule = np.array([4] * 2 + [-4] * 2 + [-10] * 2 + [-2] * 2)
        self.cd.p_el_ref_schedule = np.array([2] * 2 + [-6] * 2 + [-9] * 2 + [-1] * 2)
        prices = np.array([10] * 4 + [20] * 4)
        costs_adj = calculate_adj_costs(self.cd, "ref", prices=prices)
        self.assertEqual(2*5+2*5+1*10+1*10, costs_adj)
        costs_adj = calculate_adj_costs(self.cd, "ref", prices=prices, total_adjustments=False)
        self.assertEqual(20, costs_adj)
        self.cd.copy_schedule("ref")
        costs_adj = calculate_adj_costs(self.cd, "ref", prices=prices)
        self.assertEqual(0, costs_adj)
        return

    def test_autarky(self):
        pv = Photovoltaic(self.cd.environment, 0)
        self.cd.addEntity(pv, Point(0, 0))
        self.cd.p_el_schedule = np.array([4]*2 + [-4]*2 + [-10]*2 + [-2]*2)
        self.cd.p_el_ref_schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.p_el_schedule = - np.array([0]*2 + [8]*4 + [0]*2)
        pv.p_el_ref_schedule = - np.array([0]*2 + [8]*4 + [0]*2)

        self.assertEqual(0.5, autarky(self.cd))
        self.assertEqual(0, autarky(self.cd, timestep=2))
        self.cd.load_schedule("ref")
        self.assertEqual(1, autarky(self.cd))
        return


class TestCombinedHeatPower(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.chp = CombinedHeatPower(e, 10, 10, 0.8)
        return

    def test_calculate_co2(self):
        self.chp.p_th_heat_schedule = - np.array([10] * 8)
        self.chp.p_th_heat_ref_schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.chp, co2_emissions=co2_em)
        self.assertEqual(50.0*constants.CO2_EMISSIONS_GAS, co2)
        co2 = calculate_co2(self.chp, timestep=4, co2_emissions=co2_em)
        self.assertEqual(25.0*constants.CO2_EMISSIONS_GAS, co2)
        self.chp.load_schedule("ref")
        co2 = calculate_co2(self.chp, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_GAS, co2)
        return

    def test_lower_activation(self):
        e = get_env(4, 8)
        chp = CombinedHeatPower(e, 10, 10, 0.8, 0.5)
        m = pyomo.ConcreteModel()
        chp.populate_model(m, "integer")
        chp.update_model("integer")
        obj = pyomo.sum_product(chp.model.p_el_vars, chp.model.p_el_vars)
        obj += 2*3 * pyomo.sum_product(chp.model.p_el_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        chp.update_schedule()
        assert_equal_array(chp.p_el_schedule[:4], [-5]*4)
        return

    def test_bounds(self):
        e = get_env(8, 8)
        chp = CombinedHeatPower(e, 10, None, 0.8, 0.5)
        m = pyomo.ConcreteModel()
        chp.populate_model(m)
        chp.update_model()
        for t in range(8):
            self.assertEqual(0, chp.model.p_el_vars[t].ub)
            self.assertEqual(0, chp.model.p_th_heat_vars[t].ub)
            self.assertEqual(-10, chp.model.p_el_vars[t].lb)
            self.assertEqual(-10, chp.model.p_th_heat_vars[t].lb)

        chp = CombinedHeatPower(e, 10, 5, 0.8, 0.5)
        m = pyomo.ConcreteModel()
        chp.populate_model(m)
        chp.update_model()
        for t in range(8):
            self.assertEqual(0, chp.model.p_el_vars[t].ub)
            self.assertEqual(0, chp.model.p_th_heat_vars[t].ub)
            self.assertEqual(-5, chp.model.p_el_vars[t].lb)
            self.assertEqual(-10, chp.model.p_th_heat_vars[t].lb)
        return


class TestDeferrableLoad(unittest.TestCase):
    def setUp(self):
        self.e = get_env(6, 9)
        self.lt = [0, 1, 1, 1, 0, 1, 1, 1, 0]
        return

    def test_update_model(self):
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(self.e, 19, 10, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model)
        obj = pyomo.sum_product(dl.model.p_el_vars, dl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        dl.update_model()
        solve_model(model)

        self.assertAlmostEqual(10, pyomo.value(pyomo.sum_product(dl.model.p_el_vars)) * dl.time_slot, places=5)

        dl.timer.mpc_update()
        dl.update_model()
        solve_model(model)

        for t, c in enumerate(self.lt[1:7]):
            if c == 1:
                self.assertEqual(19, dl.model.p_el_vars[t].ub)
            else:
                self.assertEqual(0, dl.model.p_el_vars[t].ub)
        dl.update_schedule()
        assert_equal_array(dl.p_el_schedule[:7], [0, 8, 8, 8, 0, 8, 8])
        assert_equal_array(dl.p_start_schedule[:7], [False, True, False, False, False, False, False])
        return

    def test_infeasible_consumption(self):
        with self.assertWarns(UserWarning):
            feasible = DeferrableLoad(self.e, 10, 10, load_time=self.lt)
        m = pyomo.ConcreteModel()
        feasible.populate_model(m)
        feasible.update_model()
        obj = pyomo.sum_product(feasible.model.p_el_vars)
        m.o = pyomo.Objective(expr=obj)
        results = solve_model(m)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)

        m = pyomo.ConcreteModel()
        with self.assertWarns(UserWarning):
            infeasible = DeferrableLoad(self.e, 10, 10.6, load_time=self.lt)
        infeasible.populate_model(m)
        infeasible.update_model()
        obj = pyomo.sum_product(infeasible.model.p_el_vars)
        m.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(m)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)
        return

    def test_update_model_integer(self):
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(self.e, 19, 9.5, load_time=self.lt)
        m = pyomo.ConcreteModel()
        dl.populate_model(m, mode="integer")

        obj = pyomo.sum_product([0] * 2 + [1] * 2 + [0] * 2, dl.model.p_el_vars, dl.model.p_el_vars)
        m.o = pyomo.Objective(expr=obj)
        with self.assertWarns(UserWarning):
            dl.update_model(mode="integer")
        results = solve_model(m)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
        dl.update_schedule()

        assert_equal_array(np.rint(dl.p_el_schedule[:6]), [0, 19, 19, 0, 0, 0])
        for t in range(3):
            dl.timer.mpc_update()
            if t == 0:
                with self.assertWarns(UserWarning):
                    dl.update_model(mode="integer")
            else:
                dl.update_model(mode="integer")
            results = solve_model(m)
            self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
            dl.update_schedule()

        assert_equal_array(dl.p_el_schedule, [0, 19, 19, 0, 0, 0, 19, 19, 0])
        return

    def test_infeasible_integer(self):
        e = get_env(1, 9)
        model = pyomo.ConcreteModel()
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(e, 19, 9.5, load_time=self.lt)
            dl.populate_model(model, mode="integer")
            dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)

        model = pyomo.ConcreteModel()
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(self.e, 19, 19, load_time=self.lt)
            dl.populate_model(model, mode="integer")
            dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        logger = logging.getLogger("pyomo.core")
        oldlevel = logger.level
        logger.setLevel(logging.ERROR)
        results = solve_model(model)
        logger.setLevel(oldlevel)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.infeasible)

        model = pyomo.ConcreteModel()
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(self.e, 19, 19*3/4, load_time=self.lt)
            dl.populate_model(model, mode="integer")
            dl.update_model(mode="integer")
        obj = pyomo.sum_product(dl.model.p_el_vars)
        model.o = pyomo.Objective(expr=obj)
        results = solve_model(model)
        self.assertEqual(results.solver.termination_condition, TerminationCondition.optimal)
        dl.update_schedule()
        assert_equal_array(dl.p_el_schedule[:6], [0, 19, 19, 19, 0, 0])
        return

    def test_objective(self):
        with self.assertWarns(UserWarning):
            dl = DeferrableLoad(self.e, 19, 19, load_time=self.lt)
        model = pyomo.ConcreteModel()
        dl.populate_model(model)
        dl.get_objective()
        return

    def test_update_integer(self):
        e = get_env(9, 9)
        model = pyomo.ConcreteModel()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", UserWarning)
            dl = DeferrableLoad(e, 19, 19, load_time=[1] * 9)
            dl.populate_model(model, "integer")
            dl.update_model("integer")
            self.assertEqual(0, len(w))
        return


class TestFixedLoad(unittest.TestCase):
    def test_populate_model(self):
        e = get_env(2, 4)
        load = np.arange(1, 5)
        model = pyomo.ConcreteModel()
        self.fl = FixedLoad(e, method=0, demand=load)
        self.fl.populate_model(model)
        self.fl.update_model()
        model.o = pyomo.Objective(expr=pyomo.sum_product(self.fl.model.p_el_vars))
        solve_model(model)
        for t in range(2):
            self.assertEqual(self.fl.model.p_el_vars[t].value, load[t])
        return

    def test_unit_conversion(self):
        ti = Timer(step_size=1800,
                   op_horizon=48,
                   mpc_horizon=24*365,
                   mpc_step_width=1)
        we = Weather(ti)
        pr = Prices(ti)
        e = Environment(ti, we, pr)
        fl = FixedLoad(e, method=1, annual_demand=25)
        # loadcurve in Wh
        self.assertEqual(48 * 365, len(fl.loadcurve))
        self.assertAlmostEqual(25*1000, sum(fl.loadcurve)*0.5, places=5)
        # p_el_schedule in kWh
        self.assertEqual(24*365, len(fl.p_el_schedule))
        self.assertAlmostEqual(25/2, sum(fl.p_el_schedule)*0.5, delta=25/2/10)
        return


class TestElectricalEntity(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.ee = ElectricalEntity(e)
        self.ee.environment = e
        return

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.ee.populate_model(m)
        for t in range(4):
            self.ee.model.p_el_vars[t].value = t
        a = np.arange(4)

        self.ee.update_schedule()
        assert_equal_array(self.ee.p_el_schedule[:4], a)
        self.ee.timer.mpc_update()
        self.ee.update_schedule()
        assert_equal_array(self.ee.p_el_schedule[4:], a)
        return

    def test_calculate_costs(self):
        self.ee.p_el_schedule = np.array([10]*4 + [-20]*4)
        self.ee.p_el_ref_schedule = np.array([4]*4 + [-4]*4)
        prices = np.array([10]*4 + [20]*4)

        costs = calculate_costs(self.ee, prices=prices, feedin_factor=0.5)
        self.assertEqual(-100, costs)
        costs = calculate_costs(self.ee, timestep=4, prices=prices)
        self.assertEqual(100, costs)
        self.ee.load_schedule("ref")
        costs = calculate_costs(self.ee, prices=prices)
        self.assertEqual(40, costs)
        return

    def test_calculate_adj_costs(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        prices = np.array([10] * 4 + [20] * 4)
        costs_adj = calculate_adj_costs(self.ee, "ref", prices=prices)
        self.assertEqual(6*10 + 16*20, costs_adj)
        costs_adj = calculate_adj_costs(self.ee, "ref", prices=prices, total_adjustments=False)
        self.assertEqual(16 * 20, costs_adj)
        self.ee.copy_schedule("ref")
        costs_adj = calculate_adj_costs(self.ee, "ref", prices=prices)
        self.assertEqual(0, costs_adj)
        return

    def test_calculate_adj_power(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        adj_power = calculate_adj_power(self.ee, "ref")
        assert_equal_array(adj_power, [6] * 4 + [16] * 4)
        adj_power = calculate_adj_power(self.ee, "ref", total_adjustments=False)
        assert_equal_array(adj_power, [0] * 4 + [16] * 4)
        adj_power = calculate_adj_power(self.ee, "default")
        assert_equal_array(adj_power, [0] * 8)
        self.ee.load_schedule("ref")
        adj_power = calculate_adj_power(self.ee, "ref")
        assert_equal_array(adj_power, [0] * 8)
        self.ee.copy_schedule("default")
        adj_power = calculate_adj_power(self.ee, "default")
        assert_equal_array(adj_power, [0] * 8)
        return

    def test_calculate_adj_energy(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        adj_energy = calculate_adj_energy(self.ee, "ref")
        self.assertEqual(6 + 16, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "ref", total_adjustments=False)
        self.assertEqual(16, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "default")
        self.assertEqual(0, adj_energy)
        self.ee.copy_schedule(src="ref")
        adj_energy = calculate_adj_energy(self.ee, "ref")
        self.assertEqual(0, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "ref", total_adjustments=False)
        self.assertEqual(0, adj_energy)
        self.ee.load_schedule("ref")
        adj_energy = calculate_adj_energy(self.ee, "ref")
        self.assertEqual(0, adj_energy)
        adj_energy = calculate_adj_energy(self.ee, "default")
        self.assertEqual(0, adj_energy)
        return

    def test_metric_delta_g(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        g = metric_delta_g(self.ee, "ref")
        self.assertEqual(1-30/8, g)
        g = metric_delta_g(self.ee, "default")
        self.assertEqual(0, g)
        return

    def test_peak_to_average_ratio(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        ratio = peak_to_average_ratio(self.ee)
        self.assertEqual(20/5, ratio)
        self.ee.load_schedule("ref")
        with self.assertWarns(RuntimeWarning):
            ratio = peak_to_average_ratio(self.ee)
        self.assertEqual(np.inf, ratio)
        return

    def test_peak_reduction_ratio(self):
        self.ee.p_el_schedule = np.array([10] * 4 + [-20] * 4)
        self.ee.p_el_ref_schedule = np.array([4] * 4 + [-4] * 4)
        ratio = peak_reduction_ratio(self.ee, "ref")
        self.assertEqual((20-4)/4, ratio)
        self.ee.p_el_ref_schedule = np.array([4] * 8)
        ratio = peak_reduction_ratio(self.ee, "ref")
        self.assertEqual((20-4)/4, ratio)
        ratio = peak_reduction_ratio(self.ee, "default")
        self.assertEqual(0, ratio)
        self.ee.load_schedule("ref")
        ratio = peak_reduction_ratio(self.ee, "ref")
        self.assertEqual(0, ratio)
        return

    def test_self_consumption(self):
        # properly tested in CityDistrict
        self.ee.p_el_schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, self_consumption(self.ee))
        return

    def test_autarky(self):
        # properly tested in CityDistrict
        self.ee.p_el_schedule = np.array([10]*4 + [-20]*4)
        self.assertEqual(0, autarky(self.ee))
        return

    def test_objective(self):
        model = pyomo.ConcreteModel()
        self.ee.populate_model(model)
        self.ee.get_objective()
        return

    def test_new_objective(self):
        model = pyomo.ConcreteModel()
        self.ee.populate_model(model)
        for t in range(4):
            self.ee.model.p_el_vars[t].setlb(t)
            self.ee.model.p_el_vars[t].setub(t)
        self.ee.set_objective("peak-shaving")
        obj = self.ee.get_objective()
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)
        obj = self.ee.get_objective()
        self.assertEqual(sum(t**2 for t in range(4)), pyomo.value(obj))
        self.ee.set_objective("max-consumption")
        with self.assertRaises(ValueError):
            obj = self.ee.get_objective()

        model = pyomo.ConcreteModel()
        self.ee.populate_model(model)
        for t in range(4):
            self.ee.model.p_el_vars[t].setlb(t)
            self.ee.model.p_el_vars[t].setub(t)
        obj = self.ee.get_objective()
        model.o = pyomo.Objective(expr=obj)
        solve_model(model)

        self.assertAlmostEqual(3, pyomo.value(obj), 4)
        return


class TestElectricalHeater(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.eh = ElectricalHeater(e, 10, 10, 0.8)
        return

    def test_lower_activation(self):
        e = get_env(4, 8)
        eh = ElectricalHeater(e, 10, lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        eh.populate_model(m, "integer")
        eh.update_model("integer")
        obj = pyomo.sum_product(eh.model.p_el_vars, eh.model.p_el_vars)
        obj += -2 * 3 * pyomo.sum_product(eh.model.p_el_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        eh.update_schedule()
        assert_equal_array(eh.p_el_schedule[:4], [5] * 4)
        return

    def test_update_schedule(self):
        e = get_env(2, 2)
        eh = ElectricalHeater(e, 10, lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        eh.populate_model(m)
        eh.update_model()
        obj = eh.model.p_el_vars[0] - eh.model.p_el_vars[1]
        eh.model.p_el_vars[0].setlb(5.0)
        eh.model.p_el_vars[1].setub(0.05)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        eh.update_schedule()
        assert_equal_array(eh.p_el_schedule, [5, 0.05])
        assert_equal_array(eh.p_th_heat_schedule, [-5, -0.05])
        assert_equal_array(eh.p_th_heat_state_schedule, [True, False])
        return


class TestElectricVehicle(unittest.TestCase):
    def setUp(self):
        e = get_env(6, 9)
        self.ct = [1, 1, 1, 0, 0, 0, 1, 1, 1]
        self.ev = ElectricalVehicle(e, 10, 20, p_el_max_discharge=20, soc_init=0.5, charging_time=self.ct)
        return

    def test_populate_model(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        model.c1 = pyomo.Constraint(expr=self.ev.model.e_el_vars[2] == 10)
        model.c2 = pyomo.Constraint(expr=self.ev.model.e_el_vars[0] == 5)
        obj = pyomo.sum_product(self.ev.model.p_el_demand_vars, self.ev.model.p_el_demand_vars)
        model.o = pyomo.Objective(expr=obj)
        result = solve_model(model)

        self.assertEqual(31, result.Problem[0].number_of_variables)
        var_sum = pyomo.value(pyomo.quicksum(self.ev.model.p_el_vars[t] for t in range(1, 6)))
        self.assertAlmostEqual(20, var_sum, places=2)
        var_sum = pyomo.value(pyomo.quicksum(
            self.ev.model.p_el_supply_vars[t] + self.ev.model.p_el_demand_vars[t] for t in range(1, 6)))
        self.assertAlmostEqual(20, var_sum, places=2)
        return

    def test_update_model(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        self.ev.update_model()
        model.o = pyomo.Objective(expr=self.ev.get_objective())
        solve_model(model)

        self.assertAlmostEqual(10, self.ev.model.e_el_vars[2].value, places=5)
        self.assertAlmostEqual(2, self.ev.model.e_el_vars[3].value, places=5)

        self.ev.timer.mpc_update()
        self.ev.update_model()
        solve_model(model)

        for t, c in enumerate(self.ct[1:7]):
            if c:
                self.assertEqual(20, self.ev.model.p_el_demand_vars[t].ub)
                self.assertEqual(20, self.ev.model.p_el_supply_vars[t].ub)
                self.assertEqual(0, self.ev.model.p_el_drive_vars[t].ub)
            else:
                self.assertEqual(0, self.ev.model.p_el_demand_vars[t].ub)
                self.assertEqual(0, self.ev.model.p_el_supply_vars[t].ub)
                self.assertIsNone(self.ev.model.p_el_drive_vars[t].ub)
        self.assertAlmostEqual(10, self.ev.model.e_el_vars[1].value, places=5)
        self.assertAlmostEqual(2, self.ev.model.e_el_vars[2].value, places=5)
        self.assertLessEqual(1.6, self.ev.model.e_el_vars[5].value)

        self.ev.update_schedule()
        self.ev.timer.mpc_update()
        self.ev.timer.mpc_update()
        self.ev.update_model()
        solve_model(model)

        self.assertAlmostEqual(10, self.ev.model.e_el_vars[5].value, places=5)
        return

    def test_get_objective(self):
        model = pyomo.ConcreteModel()
        self.ev.populate_model(model)
        self.ev.update_model()

        obj = self.ev.get_objective(11)
        for i in range(6):
            ref = (i + 1) / 21 * 6 * 11
            coeff = obj.args[i].args[0].args[0]
            self.assertAlmostEqual(ref, coeff, places=5)
        return

    def test_no_charge_time(self):
        e = get_env(6, 9)
        ev = ElectricalVehicle(e, 37.0, 11.0)
        assert_equal_array(ev.charging_time, [1]*9)
        e = get_env(28, 96*24-12)
        ev = ElectricalVehicle(e, 37.0, 11.0)
        assert_equal_array(ev.charging_time, np.tile([1] * 24 + [0] * 48 + [1] * 24, 24)[:-12])
        return

    def test_no_discharge(self):
        model = pyomo.ConcreteModel()
        e = get_env(6, 9)
        ev = ElectricalVehicle(e, 10.0, 40.0, charging_time=self.ct)
        ev.populate_model(model)
        ev.update_model()
        model.o = pyomo.Objective(expr=ev.model.p_el_vars[0] + ev.model.p_el_vars[1])
        solve_model(model)
        ev.update_schedule()
        assert_equal_array(ev.p_el_schedule[:4], [0, 0, 5*4, 0])
        assert_equal_array(ev.p_el_demand_schedule[:4], [0, 0, 5 * 4, 0])
        assert_equal_array(ev.p_el_supply_schedule[:4], [0, 0, 0, 0])
        assert_equal_array(ev.e_el_schedule[:4], [5, 5, 10, 2])

        model = pyomo.ConcreteModel()
        e = get_env(6, 9)
        ev = ElectricalVehicle(e, 10.0, 40.0, p_el_max_discharge=8, charging_time=self.ct)
        ev.populate_model(model)
        ev.update_model()
        model.o = pyomo.Objective(expr=ev.model.p_el_vars[0] + ev.model.p_el_vars[1])
        solve_model(model)
        ev.update_schedule()
        assert_equal_array(ev.p_el_schedule[:4], [-8, -8, 9 * 4, 0])
        assert_equal_array(ev.p_el_demand_schedule[:4], [0, 0, 9 * 4, 0])
        assert_equal_array(ev.p_el_supply_schedule[:4], [8, 8, 0, 0])
        assert_equal_array(ev.e_el_schedule[:4], [3, 1, 10, 2])
        return

    def test_partial_charge(self):
        for step_size in [1, 2, 3, 6, 12]:
            with self.subTest("step_size: {}".format(step_size)):
                e = get_env(step_size, 12, step_size)
                self.ct = [1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0]
                self.ev = ElectricalVehicle(e, 10, 20, 0.5, charging_time=self.ct)
                m = pyomo.ConcreteModel()
                self.ev.populate_model(m)
                m.o = pyomo.Objective(expr=pyomo.sum_product(
                    self.ev.model.p_el_vars,
                    self.ev.model.p_el_vars
                ))
                for i in range(0, 12, step_size):
                    self.ev.update_model(m)
                    solve_model(m)
                    self.ev.update_schedule()
                    e.timer.mpc_update()
                assert_equal_array(self.ev.p_el_schedule, [5 / 3 * 4] * 3 + [0] * 3 + [8 / 3 * 4] * 3 + [0] * 3)

        step_size = 12
        e = get_env(step_size, 12, step_size)
        self.ev = ElectricalVehicle(e, 10, 20, 20, soc_init=0.5, charging_time=self.ct)
        m = pyomo.ConcreteModel()
        self.ev.populate_model(m)
        self.ev.update_model(m)
        m.o = pyomo.Objective(expr=self.ev.model.p_el_vars[2] + self.ev.model.p_el_vars[7])
        solve_model(m)
        self.ev.update_schedule()
        self.assertAlmostEqual(0, self.ev.p_el_schedule[2], 4)
        self.assertAlmostEqual(-2 * 4, self.ev.p_el_schedule[7], 4)
        return

    def test_bad_charging_times(self):
        e = get_env(3, 12)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", UserWarning)
            self.ev = ElectricalVehicle(e, 10, 8, soc_init=0.5, charging_time=[1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0])
            self.assertEqual(0, len(w))
        with self.assertWarns(UserWarning):
            self.ev = ElectricalVehicle(e, 10, 8, soc_init=0.5, charging_time=[1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0])
        with self.assertWarns(UserWarning):
            self.ev = ElectricalVehicle(e, 10, 8, soc_init=0.5, charging_time=[1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0])
        with self.assertWarns(UserWarning):
            self.ev = ElectricalVehicle(e, 10, 8, soc_init=0.5, charging_time=[1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1])
        return

    def test_inital_charging_times(self):
        for step_size in [1, 2, 3, 6, 12]:
            with self.subTest("step_size: {}".format(step_size)):
                e = get_env(step_size, 12, step_size)
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", UserWarning)
                    self.ev = ElectricalVehicle(e, 10, 8, soc_init=0.8,
                                                charging_time=[0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0])
                    self.assertEqual(0, len(w))
                m = pyomo.ConcreteModel()
                self.ev.populate_model(m)
                m.o = pyomo.Objective(expr=pyomo.sum_product(self.ev.model.p_el_vars, self.ev.model.p_el_vars))
                for i in range(0, 12, step_size):
                    self.ev.update_model(m)
                    solve_model(m)
                    self.ev.update_schedule()
                    e.timer.mpc_update()
                assert_equal_array(self.ev.p_el_schedule, [0, 8] + [0] * 4 + [8] * 4 + [0] * 2)
                assert_equal_array(self.ev.p_el_demand_schedule, [0, 8] + [0] * 4 + [8] * 4 + [0] * 2)
                assert_equal_array(self.ev.p_el_supply_schedule, [0] * 12)
                assert_equal_array(self.ev.e_el_schedule, [8, 10] + [2] * 4 + [4, 6, 8, 10] + [2] * 2)
        return


class TestHeatPump(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.hp = HeatPump(e, 10, cop=np.full(8, 11))
        return

    def test_update_model(self):
        m = pyomo.ConcreteModel()
        self.hp.populate_model(m)
        self.hp.update_model()

        c = self.hp.model.p_coupl_constr[0]
        f, l = pyomo.current.decompose_term(c.body)
        self.assertTrue(f)
        for coeff, value in l:
            if value is self.hp.model.p_el_vars[0]:
                self.assertEqual(11, coeff)
            if value is self.hp.model.p_th_heat_vars[0]:
                self.assertEqual(1, coeff)
            if value is None:
                self.assertEqual(0, coeff)
        return

    def test_lower_activation(self):
        e = get_env(4, 8)
        hp = HeatPump(e, 10, lower_activation_limit=0.5)
        m = pyomo.ConcreteModel()
        hp.populate_model(m, "integer")
        hp.update_model("integer")
        obj = pyomo.sum_product(hp.model.p_th_heat_vars, hp.model.p_th_heat_vars)
        obj += 2 * 3 * pyomo.sum_product(hp.model.p_th_heat_vars)
        m.o = pyomo.Objective(expr=obj)
        solve_model(m)
        hp.update_schedule()
        assert_equal_array(hp.p_th_heat_schedule[:4], [-5] * 4)
        return


class TestPhotovoltaic(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.pv = Photovoltaic(e, 0, 30, 0.0, 0.3)
        return

    def test_calculate_co2(self):
        self.pv.p_el_schedule = - np.array([10]*8)
        self.pv.p_el_ref_schedule = - np.array([4]*8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.pv, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_PV, co2)
        co2 = calculate_co2(self.pv, timestep=4, co2_emissions=co2_em)
        self.assertEqual(10.0*constants.CO2_EMISSIONS_PV, co2)
        self.pv.load_schedule("ref")
        co2 = calculate_co2(self.pv, co2_emissions=co2_em)
        self.assertEqual(8*constants.CO2_EMISSIONS_PV, co2)
        return

    def test_objective(self):
        model = pyomo.ConcreteModel()
        self.pv.populate_model(model)
        self.pv.get_objective()
        return


class TestPrices(unittest.TestCase):
    def test_cache(self):
        Prices.co2_price_cache = None
        Prices.da_price_cache = None
        Prices.tou_price_cache = None
        Prices.tou_price_cache_year = None
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
        return

    def test_unavailable_year(self):
        ti = Timer(op_horizon=4, mpc_horizon=8, step_size=3600,
                   initial_date=(9999, 1, 1), initial_time=(1, 0, 0))
        with self.assertWarnsRegex(UserWarning, "9999"):
            Prices(ti)
        return


class TestThermalCoolingStorage(unittest.TestCase):
    def setUp(self):
        e = get_env(3)
        self.tcs = ThermalCoolingStorage(e, 40, 0.5)
        return

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.tcs.populate_model(m)
        self.tcs.update_model()
        for t in range(3):
            self.tcs.model.p_th_cool_vars[t].setub(t)
            self.tcs.model.p_th_cool_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.tcs.model.p_th_cool_vars))
        solve_model(m)
        a = np.arange(3)

        self.tcs.update_schedule()
        assert_equal_array(self.tcs.p_th_cool_schedule, a)
        assert_equal_array(self.tcs.e_th_cool_schedule, [20, 20.25, 20.75])
        return


class TestThermalHeatingStorage(unittest.TestCase):
    def setUp(self):
        e = get_env(3)
        self.ths = ThermalHeatingStorage(e, 40, 0.5)
        return

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.ths.populate_model(m)
        self.ths.update_model()
        for t in range(3):
            self.ths.model.p_th_heat_vars[t].setub(t)
            self.ths.model.p_th_heat_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.ths.model.p_th_heat_vars))
        solve_model(m)
        a = np.arange(3)

        self.ths.update_schedule()
        assert_equal_array(self.ths.p_th_heat_schedule, a)
        assert_equal_array(self.ths.e_th_heat_schedule, [20, 20.25, 20.75])
        return


class TestThermalEntityCooling(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.tc = ThermalEntityCooling(e)
        self.tc.environment = e
        return

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.tc.populate_model(m)
        self.tc.update_model()
        for t in range(4):
            self.tc.model.p_th_cool_vars[t].setub(t)
            self.tc.model.p_th_cool_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.tc.model.p_th_cool_vars))
        solve_model(m)
        a = np.arange(4)

        self.tc.update_schedule()
        assert_equal_array(self.tc.p_th_cool_schedule[:4], a)
        self.tc.timer.mpc_update()
        self.tc.update_schedule()
        assert_equal_array(self.tc.p_th_cool_schedule[4:], a)
        return


class TestThermalEntityHeating(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8, 4)
        self.th = ThermalEntityHeating(e)
        self.th.environment = e
        return

    def test_update_schedule(self):
        m = pyomo.ConcreteModel()
        self.th.populate_model(m)
        self.th.update_model()
        for t in range(4):
            self.th.model.p_th_heat_vars[t].setub(t)
            self.th.model.p_th_heat_vars[t].setlb(t)
        m.o = pyomo.Objective(expr=pyomo.sum_product(self.th.model.p_th_heat_vars))
        solve_model(m)
        a = np.arange(4)

        self.th.update_schedule()
        assert_equal_array(self.th.p_th_heat_schedule[:4], a)
        self.th.timer.mpc_update()
        self.th.update_schedule()
        assert_equal_array(self.th.p_th_heat_schedule[4:], a)
        return


class TestSpaceCooling(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        self.load = np.arange(1, 5)
        self.sc = SpaceCooling(e, method=0, loadcurve=self.load)
        return

    def test_model(self):
        m = pyomo.ConcreteModel()
        self.sc.populate_model(m)
        self.sc.update_model()

        m.o = pyomo.Objective(expr=self.sc.model.p_th_cool_vars[0]+self.sc.model.p_th_cool_vars[1])
        r = solve_model(m)
        assert_equal_array(self.sc.p_th_cool_schedule, self.load)
        self.assertAlmostEqual(self.load[0], self.sc.model.p_th_cool_vars[0].value)
        self.assertAlmostEqual(self.load[1], self.sc.model.p_th_cool_vars[1].value)
        return


class TestSpaceHeating(unittest.TestCase):
    def setUp(self):
        e = get_env(2, 4)
        self.load = np.arange(1, 5)
        self.sh = SpaceHeating(e, method=0, loadcurve=self.load)
        return

    def test_model(self):
        m = pyomo.ConcreteModel()
        self.sh.populate_model(m)
        self.sh.update_model()

        m.o = pyomo.Objective(expr=self.sh.model.p_th_heat_vars[0]+self.sh.model.p_th_heat_vars[1])
        r = solve_model(m)
        assert_equal_array(self.sh.p_th_heat_schedule, self.load)
        self.assertAlmostEqual(self.load[0], self.sh.model.p_th_heat_vars[0].value)
        self.assertAlmostEqual(self.load[1], self.sh.model.p_th_heat_vars[1].value)
        return


class TestTimer(unittest.TestCase):
    def setUp(self):
        self.timer = Timer(mpc_horizon=192, mpc_step_width=4,
                           initial_date=(2015, 1, 15), initial_time=(12, 0, 0))
        self.timer._dt = datetime.datetime(2015, 1, 15, 13)
        return

    def test_time_in_year(self):
        self.assertEqual(1396, self.timer.time_in_year())
        self.assertEqual(1392, self.timer.time_in_year(from_init=True))
        return

    def test_time_in_week(self):
        self.assertEqual(340, self.timer.time_in_week())
        self.assertEqual(336, self.timer.time_in_week(from_init=True))
        return

    def test_time_in_day(self):
        self.assertEqual(52, self.timer.time_in_day())
        self.assertEqual(48, self.timer.time_in_day(from_init=True))
        return

    def test_more_than_one_year(self):
        for s, h, horizon in [(s, h, horizon) for s in [300, 900, 1800, 3600]
                              for h in range(int(86400*365/s)-1, int(86400*365/s)+3)
                              for horizon in ["op_horizon", "mpc_horizon"]]:
            year_horizon = int(86400 * 365 / s)
            kwargs = {"step_size": s, "initial_date": (2015, 1, 15), "initial_time": (12, 0, 0)}
            kwargs[horizon] = h
            with self.subTest(msg="step_size={} horizon={} horizon_name={}".format(s, h, horizon)):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", UserWarning)
                    t = Timer(**kwargs)
                    we = Weather(t)
                    if year_horizon < h:
                        self.assertEqual(len(w), 1, msg="No warning was thrown even though mpc_horizon / op_horizon {} "
                                                        "is larger than one year, which would be a horizon of {}"
                                         .format(h, year_horizon))
                        self.assertIn(horizon, str(w[0].message))
                        self.assertEqual(len(we.p_ambient), year_horizon)
                        self.assertEqual(len(we.phi_ambient), year_horizon)
                        self.assertEqual(len(we.q_diffuse), year_horizon)
                        self.assertEqual(len(we.q_direct), year_horizon)
                        self.assertEqual(len(we.rad_earth), year_horizon)
                        self.assertEqual(len(we.rad_sky), year_horizon)
                        self.assertEqual(len(we.v_wind), year_horizon)
                        self.assertEqual(len(we.t_ambient), year_horizon)
                        self.assertEqual(len(we.current_p_ambient), year_horizon)
                        self.assertEqual(len(we.current_phi_ambient), year_horizon)
                        self.assertEqual(len(we.current_q_diffuse), year_horizon)
                        self.assertEqual(len(we.current_q_direct), year_horizon)
                        self.assertEqual(len(we.current_rad_earth), year_horizon)
                        self.assertEqual(len(we.current_rad_sky), year_horizon)
                        self.assertEqual(len(we.current_v_wind), year_horizon)
                        self.assertEqual(len(we.current_t_ambient), year_horizon)
                    else:
                        self.assertEqual(len(w), 0)
        return


class TestWindEnergyConverter(unittest.TestCase):
    def setUp(self):
        e = get_env(4, 8)
        self.wec = WindEnergyConverter(e, np.array([0, 10]), np.array([0, 10]))
        return

    def test_calculate_co2(self):
        self.wec.p_el_schedule = - np.array([10] * 8)
        self.wec.p_el_ref_schedule = - np.array([4] * 8)
        co2_em = np.array([1111]*8)

        co2 = calculate_co2(self.wec, co2_emissions=co2_em)
        self.assertEqual(20.0*constants.CO2_EMISSIONS_WIND, co2)
        co2 = calculate_co2(self.wec, timestep=4, co2_emissions=co2_em)
        self.assertEqual(10.0*constants.CO2_EMISSIONS_WIND, co2)
        self.wec.load_schedule("ref")
        co2 = calculate_co2(self.wec, co2_emissions=co2_em)
        self.assertEqual(8.0*constants.CO2_EMISSIONS_WIND, co2)
        return

    def test_objective(self):
        model = pyomo.ConcreteModel()
        self.wec.populate_model(model)
        self.wec.get_objective()
        return


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
    opt = pyomo.SolverFactory(solvers.DEFAULT_SOLVER)
    return opt.solve(model)
