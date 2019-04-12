import unittest

import gurobipy as gp

from pycity_scheduling.classes import *


gp.setParam('outputflag', 0)


class TestBattery(unittest.TestCase):
    def setUp(self):
        e = EnvStub(3)
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


class TestElectricVehicle(unittest.TestCase):
    def setUp(self):
        e = EnvStub(6, 9)
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
        for var in model.getVars():
            # if int(var.varname[-1]) > 3:
            #     continue
            print(var.varname, var.x)

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


class EnvStub:
    def __init__(self, op_horizon, mpc_horizon=None):
        self.timer = Timer(op_horizon=op_horizon,
                           mpc_horizon=mpc_horizon,
                           mpc_step_width=1)
