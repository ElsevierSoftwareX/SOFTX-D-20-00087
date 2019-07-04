import unittest

import numpy as np
import gurobipy as gp

import pycity_scheduling.util as util


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
