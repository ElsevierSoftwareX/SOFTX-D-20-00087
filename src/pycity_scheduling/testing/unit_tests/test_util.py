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
import tempfile
import filecmp
import os
import os.path as op
import pyomo.environ as pyomo

import pycity_scheduling.util as util
import pycity_scheduling.util.factory
import pycity_scheduling.util.generic_constraints as gen_constrs
from pycity_scheduling import solvers
from pycity_scheduling.classes import *
from pycity_scheduling.data.tabula_data import tabula_building_data
from pycity_scheduling.exceptions import SchedulingError
from pycity_scheduling.util.write_schedules import schedule_to_dict, schedule_to_csv, schedule_to_json
from pycity_scheduling.util.plot_schedules import plot_entity_directory
from pycity_scheduling.algorithms import CentralOptimization


def _get_constr_count(block):
    return sum(len(data) for data in block.component_map(pyomo.Constraint).itervalues())


class TestConstraints(unittest.TestCase):
    def setUp(self):
        t = Timer(step_size=3600, op_horizon=12)
        p = Prices(t)
        w = Weather(t)
        self.env = Environment(t, w, p)
        return

    def test_lower_activation_limit(self):
        ee = ElectricalEntity(self.env)
        m = pyomo.ConcreteModel()
        ee.populate_model(m, "integer")
        o = pyomo.sum_product(ee.model.p_el_vars, ee.model.p_el_vars)
        o -= 2 * 0.3 * pyomo.sum_product(ee.model.p_el_vars)
        m.o = pyomo.Objective(expr=o)
        self.assertEqual(_get_constr_count(ee.model), 0)
        lal_constr = gen_constrs.LowerActivationLimit(ee, "p_el", 0.5, 1)

        lal_constr.apply(ee.model, "convex")
        self.assertEqual(_get_constr_count(ee.model), 0)
        opt = pyomo.SolverFactory(solvers.DEFAULT_SOLVER)
        opt.solve(m)
        ee.update_schedule()
        for i in ee.op_time_vec:
            self.assertAlmostEqual(ee.p_el_schedule[i], 0.3, 4)
            self.assertAlmostEqual(ee.p_el_state_schedule[i], 1.0, 4)

        lal_constr.apply(ee.model, "integer")
        self.assertEqual(_get_constr_count(ee.model), 12*2)

        opt.solve(m)
        ee.update_schedule()
        for i in ee.op_time_vec:
            self.assertAlmostEqual(ee.p_el_schedule[i], 0.5, 4)
            self.assertAlmostEqual(ee.p_el_state_schedule[i], 1.0, 4)
        return


class TestFactory(unittest.TestCase):
    def setUp(self):
        t = Timer()
        p = Prices(t)
        w = Weather(t)
        self.env = Environment(t, w, p)
        self.sd = {'SFH.2002': 0.43, 'SFH.2010': 0.47, 'SFH.2016': 0.1}
        self.hd = {'HP': 0.31, 'BL': 0.34, 'EH': 0.35}
        self.dd = {'FL': 1, 'DL': 0.2, 'EV': 0.3, 'BAT': 0.5, 'PV': 0.8}
        self.md = {'MFH.2002': 0.99, 'MFH.2010': 0.01, 'MFH.2016': 0.0}
        return

    def test_distribution(self):
        district = util.factory.generate_tabula_district(self.env, 5, 2, self.sd, self.hd, self.dd, self.md, self.hd,
                                                         self.dd)
        buildings = [b for b in district.get_lower_entities() if type(b) == Building]
        for i, building in enumerate(self.sd.keys()):
            amount = [2, 2, 1][i]
            self.assertEqual(amount, sum(1 for b in buildings if b.building_type ==
                                         tabula_building_data[building]['building_type']))
        for i, building in enumerate(self.md.keys()):
            amount = [2, 0, 0][i]
            self.assertEqual(amount, sum(1 for b in buildings if b.building_type ==
                                         tabula_building_data[building]['building_type']))
        for i, h_id in enumerate(self.hd.keys()):
            amount = [1, 3, 3][i]
            self.assertEqual(amount, sum(1 for b in buildings for e in b.get_entities() if
                                         type(e) == heating_devices[h_id]))
        sfhs = [b for b in buildings if b.building_type.find("SFH") != -1]
        mfhs = [b for b in buildings if b.building_type.find("MFH") != -1]
        number_ap_sfh = sum(1 for b in sfhs for e in b.get_lower_entities() if type(e) == Apartment)
        number_ap_mfh = sum(1 for b in mfhs for e in b.get_lower_entities() if type(e) == Apartment)
        assert len(sfhs) == number_ap_sfh == 5
        assert len(mfhs) == 2
        for d_id, share in self.dd.items():
            if d_id in ["FL", "DL", "EV"]:
                amount_sfh = round(share * number_ap_sfh)
                amount_mfh = round(share * number_ap_mfh)
            elif d_id in ["BAT", "PV"]:
                amount_sfh = round(share * 5)
                amount_mfh = round(share * 2)
            else:
                raise ValueError("Unknown Type {}".format(d_id))
            self.assertEqual(amount_sfh, sum(1 for b in sfhs for e in b.get_entities() if
                                         type(e) == all_entities[d_id]))
            self.assertEqual(amount_mfh, sum(1 for b in mfhs for e in b.get_entities() if
                                         type(e) == all_entities[d_id]))

        op = CentralOptimization(district)
        op.solve(beta=0)
        return


class TestWriteSchedules(unittest.TestCase):
    def setUp(self):
        t = Timer(op_horizon=2)
        p = Prices(t)
        w = Weather(t)
        e = Environment(t, w, p)
        self.cd = CityDistrict(e)
        self.bd = Building(e)
        self.cd.p_el_schedule[:] = [5, 10]
        self.bd.load_schedule("ref")
        self.bd.p_el_schedule[:] = [2, 8]
        return

    def test_to_dict_1(self):
        d = schedule_to_dict([self.cd, self.bd], "default")
        self.assertSetEqual(set([str(self.cd), str(self.bd)]), set(d.keys()))
        d_cd = d[str(self.cd)]
        self.assertSetEqual(set(["default"]), set(d_cd.keys()))
        d_cd_d = d_cd["default"]
        self.assertSetEqual(set(["p_el"]), set(d_cd_d.keys()))
        assert np.allclose([5, 10], d_cd_d["p_el"])
        d_bd = d[str(self.bd)]
        self.assertSetEqual(set(["default"]), set(d_bd.keys()))
        d_bd_d = d_bd["default"]
        self.assertSetEqual(set(["p_el", "p_th_heat", "p_th_cool"]), set(d_bd_d.keys()))
        assert np.allclose([0, 0], d_bd_d["p_el"])
        assert np.allclose([0, 0], d_bd_d["p_th_heat"])
        assert np.allclose([0, 0], d_bd_d["p_th_cool"])
        return

    def test_to_dict_2(self):
        d = schedule_to_dict([self.cd, self.bd])
        self.assertSetEqual(set([str(self.cd), str(self.bd)]), set(d.keys()))
        d_cd = d[str(self.cd)]
        self.assertSetEqual(set(["default"]), set(d_cd.keys()))
        d_cd_d = d_cd["default"]
        self.assertSetEqual(set(["p_el"]), set(d_cd_d.keys()))
        assert np.allclose([5, 10], d_cd_d["p_el"])
        d_bd = d[str(self.bd)]
        self.assertSetEqual(set(["ref"]), set(d_bd.keys()))
        d_bd_d = d_bd["ref"]
        self.assertSetEqual(set(["p_el", "p_th_heat", "p_th_cool"]), set(d_bd_d.keys()))
        assert np.allclose([2, 8], d_bd_d["p_el"])
        assert np.allclose([0, 0], d_bd_d["p_th_heat"])
        assert np.allclose([0, 0], d_bd_d["p_th_cool"])
        return

    def test_to_dict_3(self):
        d = schedule_to_dict([self.cd, self.bd], ["default", "ref"])
        self.assertSetEqual(set([str(self.cd), str(self.bd)]), set(d.keys()))
        d_cd = d[str(self.cd)]
        self.assertSetEqual(set(["default", "ref"]), set(d_cd.keys()))
        d_cd_d = d_cd["default"]
        self.assertSetEqual(set(["p_el"]), set(d_cd_d.keys()))
        assert np.allclose([5, 10], d_cd_d["p_el"])
        d_cd_d = d_cd["ref"]
        self.assertSetEqual(set(["p_el"]), set(d_cd_d.keys()))
        assert np.allclose([0, 0], d_cd_d["p_el"])
        d_bd = d[str(self.bd)]
        self.assertSetEqual(set(["default", "ref"]), set(d_bd.keys()))
        d_bd_d = d_bd["default"]
        self.assertSetEqual(set(["p_el", "p_th_heat", "p_th_cool"]), set(d_bd_d.keys()))
        assert np.allclose([0, 0], d_bd_d["p_el"])
        assert np.allclose([0, 0], d_bd_d["p_th_heat"])
        assert np.allclose([0, 0], d_bd_d["p_th_cool"])
        d_bd_d = d_bd["ref"]
        self.assertSetEqual(set(["p_el", "p_th_heat", "p_th_cool"]), set(d_bd_d.keys()))
        assert np.allclose([2, 8], d_bd_d["p_el"])
        assert np.allclose([0, 0], d_bd_d["p_th_heat"])
        assert np.allclose([0, 0], d_bd_d["p_th_cool"])
        return

    def test_schedule_to_json(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            schedule_to_json([self.cd, self.bd], op.join(tmpdirname, "test"), ["default", "ref"])
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test.json"))))
            schedule_to_json([self.cd], op.join(tmpdirname, "test2.json"), "default")
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test2.json"))))
            with open(op.join(tmpdirname, "test3.json"), "w") as test3:
                schedule_to_json([self.cd], test3, "default")
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test3.json"))))
            self.assertFalse(filecmp.cmp(op.join(tmpdirname, "test.json"),
                                         op.join(op.join(tmpdirname, "test2.json")),
                                         shallow=False))
            self.assertTrue(filecmp.cmp(op.join(tmpdirname, "test2.json"),
                                        op.join(op.join(tmpdirname, "test3.json")),
                                        shallow=False))
        return

    def test_schedule_to_csv(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            schedule_to_csv([self.cd, self.bd], op.join(tmpdirname, "test"), ';', ["default", "ref"])
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test.csv"))))
            schedule_to_csv([self.cd], op.join(tmpdirname, "test2.csv"), ';', "default")
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test2.csv"))))
            schedule_to_csv([self.cd], op.join(tmpdirname, "test3.csv"), ',', "default")
            self.assertTrue(op.exists(op.join(op.join(tmpdirname, "test3.csv"))))
            self.assertFalse(filecmp.cmp(op.join(tmpdirname, "test.csv"),
                                         op.join(op.join(tmpdirname, "test2.csv")),
                                         shallow=False))
            self.assertTrue(filecmp.cmp(op.join(tmpdirname, "test2.csv"),
                                        op.join(op.join(tmpdirname, "test3.csv")),
                                        shallow=False))
        return


class TestPlotSchedules(unittest.TestCase):
    def setUp(self):
        t = Timer(op_horizon=2)
        p = Prices(t)
        w = Weather(t)
        e = Environment(t, w, p)
        self.cd = CityDistrict(e)
        self.bd = Building(e)
        self.cd.addEntity(entity=self.bd, position=[0, 0])
        self.cd.p_el_schedule[:] = [5, 10]
        self.bd.load_schedule("ref")
        self.bd.p_el_schedule[:] = [2, 8]
        self.ap = Apartment(e)
        self.bd.addEntity(self.ap)
        return

    def test_plot_into_dir(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            plot_entity_directory(self.cd, schedule=["default", "ref"], directory_path=op.join(tmpdirname, "test"),
                                  levels=0)
            cd_set = set([str(self.cd) + ".png"])
            bd_set = cd_set | set([str(self.bd)])
            ap_set = set([str(self.bd) + ".png", str(self.ap) + ".png"])
            self.assertSetEqual(cd_set, set(os.listdir(op.join(tmpdirname, "test"))))

            plot_entity_directory(self.cd, schedule="default", directory_path=op.join(tmpdirname, "test2"),
                                  levels=1)
            self.assertSetEqual(cd_set | set([str(self.bd) + ".png"]), set(os.listdir(op.join(tmpdirname, "test2"))))

            plot_entity_directory(self.cd, schedule="default", directory_path=op.join(tmpdirname, "test3"),
                                  levels=2)
            self.assertSetEqual(bd_set, set(os.listdir(op.join(tmpdirname, "test3"))))
            self.assertSetEqual(ap_set, set(os.listdir(op.join(tmpdirname, "test3", str(self.bd)))))

            plot_entity_directory(self.cd, schedule="default", directory_path=op.join(tmpdirname, "test4"))
            self.assertSetEqual(bd_set, set(os.listdir(op.join(tmpdirname, "test4"))))
            self.assertSetEqual(ap_set, set(os.listdir(op.join(tmpdirname, "test4", str(self.bd)))))

            files = list(cd_set)
            files.extend((op.join(str(self.bd), p) for p in ap_set))
            match, missmatch, errors = filecmp.cmpfiles(op.join(tmpdirname, "test3"), op.join(tmpdirname, "test4"),
                                                        files, shallow=False)

            self.assertListEqual(files, match)
            self.assertListEqual([], missmatch)
            self.assertListEqual([], errors)
        return


class TestSubpackage(unittest.TestCase):

    def test_compute_profile(self):
        t = TimerStub()

        with self.assertRaises(ValueError):
            util.compute_profile(t, [1, 0])
        with self.assertRaises(ValueError):
            util.compute_profile(t, [], 'hmm')
        profile = util.compute_profile(t, [0, 1, 0, 1])
        self.assertTrue(np.array_equal([0, 1, 0, 1], profile))
        daily = [0]*11 + [1, 0]*2 + [1]*9
        profile = util.compute_profile(t, daily, 'daily')
        self.assertTrue(np.array_equal([0, 1, 0, 1], profile))
        weekly = [0]*24 + [0]*11 + [1, 0]*2 + [1]*9 + [0]*120
        profile = util.compute_profile(t, weekly, 'weekly')
        self.assertTrue(np.array_equal([0, 1, 0, 1], profile))
        return

    def test_value_extraction(self):
        v = pyomo.Var(domain=pyomo.Reals)
        with self.assertRaises(ValueError):
            util.extract_pyomo_values(v)

        m = pyomo.ConcreteModel()
        opt = pyomo.SolverFactory(solvers.DEFAULT_SOLVER)

        m.v = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.v == 1.0)
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(1, e)
        self.assertIs(float, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(pyomo.RangeSet(1, 2), domain=pyomo.Reals)
        opt.solve(m)

        m.v[1].value = 1
        m.v[2].value = 2
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(0, e[0])
        self.assertEqual(0, e[1])
        self.assertEqual('f', e.dtype.kind)

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(4, 5))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(4, e)

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(4.1, 4.3))
        opt.solve(m)
        with self.assertRaises(SchedulingError):
            util.extract_pyomo_values(m.v)

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(pyomo.RangeSet(1, 2), domain=pyomo.Binary, bounds=(0.1, 0.9))
        opt.solve(m)
        with self.assertRaises(SchedulingError):
            util.extract_pyomo_values(m.v)

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(3.9, 4.3))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(4, e)
        self.assertIs(int, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers)
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(0, e)
        self.assertIs(int, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(None, -5))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(-5, e)
        self.assertIs(int, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(-10, -2))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(-2, e)
        self.assertIs(int, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(domain=pyomo.Integers, bounds=(2, 10))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(2, e)
        self.assertIs(int, type(e))

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(pyomo.RangeSet(1, 2), domain=pyomo.Binary)
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(0, e[0])
        self.assertEqual(0, e[1])
        self.assertEqual('b', e.dtype.kind)

        m = pyomo.ConcreteModel()
        m.a = pyomo.Var(domain=pyomo.Reals)
        m.c = pyomo.Constraint(expr=m.a == 1.0)
        m.v = pyomo.Var(pyomo.RangeSet(1, 2), domain=pyomo.Binary, bounds=(1, None))
        opt.solve(m)
        e = util.extract_pyomo_values(m.v)
        self.assertEqual(1, e[0])
        self.assertEqual(1, e[1])
        self.assertEqual('b', e.dtype.kind)
        return


class TimerStub:
    def __init__(self):
        self.time_discretization = 3600
        self.simu_horizon = 4

    @staticmethod
    def time_in_week(from_init):
        if not from_init:
            raise ValueError
        return 36

    @staticmethod
    def time_in_day(from_init):
        if not from_init:
            raise ValueError
        return 12
