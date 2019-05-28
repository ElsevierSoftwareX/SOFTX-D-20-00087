import unittest

import numpy as np

import pycity_scheduling.util as util


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
