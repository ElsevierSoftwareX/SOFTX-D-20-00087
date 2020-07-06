import unittest

import numpy as np
import pyomo.environ as pyomo
from pyomo.opt import SolverStatus, TerminationCondition

import pycity_scheduling.util as util
import pycity_scheduling.util.generic_constraints as gen_constrs
from pycity_scheduling.classes import *
import pycity_scheduling.util.factory
from pycity_scheduling.data.tabula_data import tabula_building_data

def _get_constr_count(block):
    return sum(len(data) for data in block.component_map(pyomo.Constraint).itervalues())

class TestConstraints(unittest.TestCase):
    def setUp(self):
        t = Timer()
        p = Prices(t)
        w = Weather(t)
        self.env = Environment(t, w, p)

    def test_lower_activation_limit(self):
        ee = ElectricalEntity(self.env)
        m = pyomo.ConcreteModel()
        ee.populate_model(m, "integer")
        o = pyomo.sum_product(ee.model.P_El_vars, ee.model.P_El_vars)
        o -= 2 * 0.3 * pyomo.sum_product(ee.model.P_El_vars)
        m.o = pyomo.Objective(expr=o)
        self.assertEqual(_get_constr_count(ee.model), 0)
        lal_constr = gen_constrs.LowerActivationLimit(ee, "P_El", 0.5, 1)

        lal_constr.apply(ee.model, "convex")
        self.assertEqual(_get_constr_count(ee.model), 0)
        opt = pyomo.SolverFactory('gurobi')
        opt.solve(m)
        ee.update_schedule()
        for i in ee.op_time_vec:
            self.assertEqual(ee.P_El_Schedule[i], 0.3)
            self.assertEqual(ee.P_El_State_Schedule[i], 1.0)

        lal_constr.apply(ee.model, "integer")
        self.assertEqual(_get_constr_count(ee.model), 96*2)

        opt.solve(m)
        ee.update_schedule()
        for i in ee.op_time_vec:
            self.assertEqual(ee.P_El_Schedule[i], 0.5)
            self.assertEqual(ee.P_El_State_Schedule[i], 1.0)


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

        m = util.populate_models(district, "convex", "central", None)[0]
        district.update_model("convex")
        for node_id, node in district.nodes.items():
            node['entity'].update_model("convex")
        m.o = pyomo.Objective(expr=district.get_objective())

        # check feasibility
        opt = pyomo.SolverFactory('gurobi')
        results = opt.solve(m)
        self.assertEqual(TerminationCondition.optimal, results.solver.termination_condition)



class TestSubpackage(unittest.TestCase):
    def test_get_uncertainty(self):
        # Warning: This is a statistical test. There is always a chance it may
        # fail, even if the function is working correctly. If so, try running
        # again or increse `n`.
        import statistics as stat
        n = 10000
        a = util.get_uncertainty(.1, n)
        msg = "Might be a statistical error, try running again."
        self.assertAlmostEqual(.1, stat.stdev(a), 2, msg)

    def test_get_incr_uncertainty(self):
        # Warning: This is a statistical test. There is always a chance it may
        # fail, even if the function is working correctly. If so, try running
        # again or increse `n`.
        import statistics as stat
        n = 1000
        a = np.ones(n)
        b = np.ones(n)
        msg = "Might be a statistical error, try running again."

        for i in range(n):
            u = util.get_incr_uncertainty(.1, 20, 10)
            a[i] = u[-1]
            b[i] = u[-10]
        self.assertAlmostEqual(.1, stat.stdev(a), 2, msg)
        self.assertAlmostEqual(.01, stat.stdev(b), 3, msg)

        u = util.get_incr_uncertainty(.1, 20, 10)
        self.assertEqual(20, len(u))
        self.assertTrue(all(u[:10] == 1))

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


class TimerStub:
    def __init__(self):
        self.timeDiscretization = 3600
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
