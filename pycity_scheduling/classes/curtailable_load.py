import warnings
import gurobipy as gurobi
import pycity_base.classes.demand.ElectricalDemand as ed
import numpy as np

from .electrical_entity import ElectricalEntity


class CurtailableLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pycity class ElectricalDemand for scheduling purposes.
    """

    def __init__(self, environment, P_El_Nom, max_curtailment,
                 max_low=None, min_full=None):
        """Initialize a curtailable load.

        Parameters
        ----------
        environment : Environment
            Common Environment instance.
        P_El_Nom : float
            Nominal electric power in [kW].
        max_curtailment : float
            Maximal Curtailment of the load
        max_low : int, optional
            Maximum amount of timesteps the curtailable load can stay under
            nominal load
        min_full : int, optional
            Minimum amount of timesteps the curtailable load has to stay at
            nominal operation level when switching to the nominal operation
            level
        """
        shape = environment.timer.timestepsTotal
        super(CurtailableLoad, self).__init__(environment, 0, np.zeros(shape))
        self._long_ID = "CUL_" + self._ID_string

        self.P_El_Nom = P_El_Nom
        self.max_curt = max_curtailment
        if max_low is not None or min_full is not None:
            assert max_low is not None
            assert min_full is not None
            assert min_full >= 1
            assert max_low >= 0
            assert self.simu_horizon > min_full + max_low
        self.max_low = max_low
        self.min_full = min_full
        self.P_El_Curt = self.P_El_Nom * self.max_curt
        self.P_State_vars = []
        self.P_State_schedule = np.empty(self.simu_horizon, bool)
        self.constr_previous_state = []
        self.constr_previous = []

    def populate_model(self, model, mode="convex"):
        """Add variables to Gurobi model

        Call parent's `populate_model` method and set variables upper bounds to
        the loadcurve and lower bounds to s`elf.P_El_Min`.

        Parameters
        ----------
        model : gurobi.Model
        mode : str, optional
            Specifies which set of constraints to use
            - `convex`  : Use linear constraints
            - `integer`  : Uses integer variables for max_off and min_on constraints if necessary
        """
        super(CurtailableLoad, self).populate_model(model, mode)

        if mode == "convex" or mode == "integer":
            for t in self.op_time_vec:
                self.P_El_vars[t].lb = self.P_El_Curt
                self.P_El_vars[t].ub = self.P_El_Nom

            if self.max_low is None:
                # if max_low is not set the entity can choose P_State freely.
                # as a result no constraints are required
                pass
            elif self.max_low == 0:
                # if max_low is zero the P_State_vars would have to  always be one
                # this results in operation at always 100%.
                # the following bound is enough to represent this behaviour
                for t in self.op_time_vec:
                    self.P_El_vars[t].lb = self.P_El_Nom
            elif mode == "integer":
                # generate integer constraints for max_low min_full values

                # create binary variables representing the state if the device is operating at full level
                for t in self.op_time_vec:
                    self.P_State_vars.append(model.addVar(
                        vtype=gurobi.GRB.BINARY,
                        name="%s_Mode_at_t=%i"
                             % (self._long_ID, t + 1)
                    ))
                model.update()

                # coupling the state variable to the electrical variable
                # since operation infinitly close to 100% can be chosen by the entity to create a state
                # of zero, coupling in one direction is sufficient.
                for t in self.op_time_vec:
                    model.addConstr(
                        self.P_State_vars[t] * self.P_El_Nom <= self.P_El_vars[t]
                    )

                # creat constraints which can be used by update_model to take previous states into account.
                # update_schedule only needs to modify RHS which should be faster than deleting and creating
                # new constraints
                max_overlap = max(self.max_low, self.min_full - 1)
                for t in range(1, max_overlap + 1):
                    self.constr_previous_state.append(model.addConstr(
                        gurobi.quicksum(self.P_State_vars[:t]) >= -gurobi.GRB.INFINITY
                    ))

                # add constraints forcing the entity to operate at least once at 100% between every range
                # of max_low + 1 in the op_horizon
                for t in self.op_time_vec:
                    next_states = self.P_State_vars[t:t + self.max_low + 1]
                    assert 1 <= len(next_states) <= self.max_low + 1
                    if len(next_states) == self.max_low + 1:
                        model.addConstr(
                            gurobi.quicksum(next_states) >= 1
                        )

                # add constraints to operate at a minimum of min_full timestaps at 100% when switching
                # from the state 0 to the state 1
                if self.min_full > 1:
                    for t in self.op_time_vec[:-2]:
                        next_states = self.P_State_vars[t + 2: t + self.min_full + 1]
                        assert 1 <= len(next_states) <= self.min_full - 1
                        model.addConstr(
                            (self.P_State_vars[t + 1] - self.P_State_vars[t]) * len(next_states) <=
                            gurobi.quicksum(next_states)
                        )
            else:
                # generate relaxed constraints with max_off min_on values
                width = self.min_full + self.max_low
                for t in self.op_time_vec[:-width + 1]:
                    next_vars = self.P_El_vars[t:t + width]
                    assert len(next_vars) == width
                    model.addConstr(
                        gurobi.quicksum(next_vars) >=
                        self.P_El_Nom * self.min_full + self.P_El_Curt * self.max_low
                    )

                # creat constraints which can be used by update_model to take previous P_El values into
                # account. update_schedule only needs to modify RHS which should be faster than deleting
                # and creating new constraints
                for t in range(1, self.max_low + self.min_full):
                    self.constr_previous.append(model.addConstr(
                        gurobi.quicksum(self.P_El_vars[:t]) >= -gurobi.GRB.INFINITY
                    ))
        else:
            raise ValueError(
                "Mode %s is not implemented by CHP." % str(mode)
            )

    def upate_model(self, model, mode="convex"):
        super(CurtailableLoad, self).update_model(model, mode)
        timestep = self.timer.currentTimestep

        # if the timestep is zero a perfect initial constraint is assumed.
        # this results in no constraints
        if timestep != 0:
            # if binary vars are used, constraints need to be updated.
            if len(self.constr_previous_state) > 0:
                # reset all constraints which could have been previously been modified.
                for constr in self.constr_previous_state:
                    constr.RHS = -gurobi.GRB.INFINITY

                # if the device was operating at 100% in the previous timestep
                if self.P_State_schedule[timestep - 1]:
                    # count the last timesteps it was operating at 100%
                    on_ts = 1
                    while (timestep - on_ts - 1) >= 0 and self.P_State_schedule[timestep - on_ts - 1]:
                        on_ts += 1
                    if timestep - on_ts - 1 < 0:
                        # if the device was operating at 100% back until timestep 0,
                        # perfect initial state is assumed resulting in no constraints
                        pass
                    else:
                        # calculate the remaining timesteps the device needs to operate
                        # at 100%
                        remaining_ons = self.min_full - on_ts
                        if remaining_ons <= 0:
                            # if device was operating longer than min_full at 100%,
                            # no constraints need to be created
                            pass
                        else:
                            # create constraints by modifying RHS
                            self.constr_previous_state[remaining_ons - 1].RHS = remaining_ons
                # if the device was not operating at 100% in the previous timestep
                else:
                    # count the last timesteps it was operating under 100%
                    off_ts = 1
                    while (timestep - off_ts - 1) >= 0 and not self.P_State_schedule[timestep - off_ts - 1]:
                        assert off_ts <= self.max_low
                        off_ts += 1
                    # calculate the timesteps in which the device has to operate at 100% in
                    overlap = self.max_low - off_ts + 1
                    # create constraints by modifying RHS
                    self.constr_previous_state[overlap - 1].RHS = 1

            elif len(self.constr_previous) > 0:
                # no resets are required, because previously modified RHSs will be modified
                # again
                width = self.min_full + self.max_low
                for t in range(max(0, timestep - width + 1), timestep, 1):
                    # calculate the required power between previous and current timesteps
                    required = self.P_El_Nom * self.min_full + self.P_El_Curt * self.max_low
                    # calculate already consumed power
                    already_done = sum(self.P_El_Schedule[t:timestep])
                    # create constraints by modifying RHS
                    self.constr_previous[width - (timestep - t) - 1].RHS = \
                         required - already_done


    def update_schedule(self):
        super(CurtailableLoad, self).update_schedule()
        timestep = self.timer.currentTimestep
        self.P_State_schedule[timestep:timestep + self.op_horizon] \
            = [np.isclose(var.X, self.P_El_Nom) for var in self.P_El_vars]

    def get_objective(self, coeff=None, coeff_flex=None):
        """Objective function for entity level scheduling.

        Return the objective function of the curtailable load wheighted with
        coeff. Quadratic term minimizing the deviation from the loadcurve.

        Parameters
        ----------
        coeff : float, optional
            Coefficient for the objective function.
            Represents the price for 1kWh of electricity
        coeff_flex : float, optional
            Coefficient for the objective function.
            Represents the expected price for shifting 1kWh after the op_horizon
        Returns
        -------
        gurobi.QuadExpr :
            Objective function.
        """
        obj = gurobi.LinExpr()
        if coeff is not None:
            obj.addTerms(
                [coeff] * self.op_horizon,
                self.P_El_vars
            )
        if len(self.P_State_vars) > 0 and coeff_flex is not None:
            # giving flexibility a price is required in order to favor some outcomes over others
            # for example the outcome which ends with
            # ... 50% 50% 50% 100%
            # should be favour over the outcome which ends with
            # ... 50% 50% 100% 50%
            # because the first outcome allow for more possible schedules to be generated in the
            # next op_horizion

            # in order to model the benefit a price to flexibility can be given

            # calculate end possibilities when minimal electricity is used
            end_possibilities = [0] * self.max_low + [1] * self.min_full
            width = len(end_possibilities)
            end_possibilities = np.fromiter((end_possibilities[(j+i) % width] for i in range(width)
                                             for j in range(width)), dtype=int).reshape((width, width))
            def count_possibilities(row):
                # row are possible states in the previous op_horizion
                # count possibilities in the first slot in the next op_horzton
                # only works with optimal end_possibilites
                if row[0] == 1:
                    count = 0
                    for i in range(0, self.min_full + 1):
                        if row[i] == 1:
                            count += 1
                        else:
                            count = self.min_full - count
                            assert 0 <= count < self.min_full
                            return count
                else:
                    count = 1
                    for i in range(0, self.max_low + 1):
                        if row[i] == 0:
                            count += 1
                        else:
                            return count
                raise ValueError

            # give scores to the end possibilities between -1 and 0
            score = np.fromiter((-count_possibilities(end_possibilities[i]) for i in range(width)), dtype=float)
            score = score/max(abs(score))
            # calculate constants which should be given to the previous states in order
            # to model this benefit with last P_State_vars and constats
            A = end_possibilities

            # self.P_State_vars[-width:] doesnt need to be used and can be replaced with a
            # constant to the flex_obj term
            A[:, 0] = np.ones(width)

            coeffs, _, _, _ = np.linalg.lstsq(A, score, rcond=-1)

            flex_obj = gurobi.LinExpr()
            flex_obj += coeffs[0]
            flex_obj.addTerms(
                coeffs[1:],
                self.P_State_vars[-width+1:]
            )
            obj += coeff_flex * (self.P_El_Nom - self.P_El_Curt) * flex_obj
        return obj

    def update_deviation_model(self, model, timestep, mode=""):
        """Update deviation model for the current timestep."""
        if mode == 'full':
            self.P_El_Act_var.lb = self.P_El_Curt
            self.P_El_Act_var.ub = self.P_El_Nom
        else:
            self.P_El_Act_var.lb = self.P_El_Schedule[timestep]
            self.P_El_Act_var.ub = self.P_El_Schedule[timestep]
