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
import datetime
import calendar
import warnings
import pycity_base.classes.timer as ti


class Timer(ti.Timer):
    """
    Extension of pyCity_base class Timer for scheduling purposes

    Parameters
    ----------
    step_size : int, optional
        Number of seconds in one time step.
    op_horizon : int, optional
        Number of time steps used in one scheduling optimization.
    mpc_horizon : int, optional
        Number of time steps in whole simulation. All data must be
        available for this time. If `None` set value to `op_horizon`.
    mpc_step_width: int, optional
        Number of timesteps between two optimizations in MPC. If None set
        value to `op_horizon`.
    initial_date : tuple, optional
        Initial date in the format (year, month, day).
    initial_time : tuple, optional
        Initial time in the format (hour, minute, second).

    Notes
    -----
    - This class' behaviour may differ from the one of the baseclass, as it
      keeps an actual date rather than a relative counter only
    """

    def __init__(self, step_size=900, op_horizon=96,
                 mpc_horizon=None, mpc_step_width=None,
                 initial_date=(2015, 1, 1), initial_time=(0, 0, 0)):
        a, b = divmod(3600, step_size)
        if b != 0:
            raise ValueError(
                "`step_size` must be a factor of 3600 (1h)."
            )
        self._dt = datetime.datetime(
            initial_date[0], initial_date[1], initial_date[2],
            initial_time[0], initial_time[1], initial_time[2]
        )
        dt0 = datetime.datetime(self._dt.year, 1, 1)
        initial_day = dt0.weekday() + 1
        a, b = divmod((self._dt - dt0).total_seconds(), step_size)
        if b > 0:
            raise ValueError(
                "The difference from the starting point of the simulation "
                "to the beginning of the year must be a multiple of "
                "`time_discretization`."
            )
        # Workaround to make the weather instance calculate values for a whole
        # year.
        horizon = int(365 * 24 * 3600 / step_size)
        # if calendar.isleap(initial_date[0]):
        #     horizon += 24 * 3600 / step_size
        super(Timer, self).__init__(time_discretization=step_size,
                                    timesteps_used_horizon=op_horizon,
                                    timesteps_horizon=horizon,
                                    timesteps_total=horizon,
                                    initial_day=initial_day)

        self.time_slot = step_size / 3600
        self._init_dt = self._dt
        if mpc_horizon is None:
            self.simu_horizon = op_horizon
        else:
            self.simu_horizon = mpc_horizon
        if self.simu_horizon > horizon:
            horizon_name = "op_horizon" if mpc_horizon is None else "mpc_horizon"
            warnings.warn("`{}` indicates a horizon larger than one year. pyCity_base is currently not able to "
                          "produce forecasts for such a duration.".format(horizon_name), UserWarning)
        if mpc_step_width is None:
            self.mpc_step_width = op_horizon
        else:
            self.mpc_step_width = mpc_step_width

    @property
    def datetime(self):
        """
        The datetime of the current timestep.
        """
        return self._dt

    @property
    def date(self):
        """
        The date of the current timestep.
        """
        return datetime.date(self._dt.year, self._dt.month, self._dt.day)

    @property
    def is_leap(self):
        """
        If the year of the current timestep is a leap year.
        """
        return calendar.isleap(self._dt.year)

    @property
    def year(self):
        """
        The year of the current timestep.
        """
        return self._dt.year

    @property
    def month(self):
        """
        The month of the current timestep.
        """
        return self._dt.month

    @property
    def day(self):
        """
        The day of the month for the current timestep.
        """
        return self._dt.day

    @property
    def weekday(self):
        """
        The weekday of the current timestep.
        """
        return self._dt.weekday()

    @property
    def time(self):
        """
        The time for the current timestep.
        """
        return datetime.time(self._dt.hour, self._dt.minute, self._dt.second)

    @property
    def hour(self):
        """
        The hour of the current timestep.
        """
        return self._dt.hour

    @property
    def minute(self):
        """
        The minute of the current timestep.
        """
        return self._dt.minute

    @property
    def second(self):
        """
        The second of the current timestep.
        """
        return self._dt.second

    def print_datetime(self):
        """
        Print the datetime for the current timestep.
        """
        return str(self._dt)

    def mpc_update(self):
        """
        Update Timer for MPC.

        Move `self.mpc_step_width` timesteps forward.
        """
        self.current_timestep += self.mpc_step_width
        self._dt += datetime.timedelta(
            seconds=self.time_discretization*self.mpc_step_width
        )

        # update values from parent class
        self.current_weekday = self._dt.weekday() + 1
        self.current_day_weekend = self.current_weekday >= 6
        self.current_day = self.time_in_year("days")
        return

    def op_update(self):
        """
        Update Timer for a normal scheduling optimization.

        Go `self.timesteps_used_horizon` timesteps forward.
        """
        self.current_timestep += self.timesteps_used_horizon
        self._dt += datetime.timedelta(
            seconds=self.time_discretization*self.timesteps_used_horizon
        )

        # update values from parent class
        self.current_weekday = self._dt.weekday() + 1
        self.current_day_weekend = self.current_weekday >= 6
        self.current_day = self.time_in_year("days")
        return

    def reset(self):
        """
        Reset the Timer to the initial state.
        """
        self._dt = self._init_dt
        self.current_timestep = 0
        self.current_weekday = self._dt.weekday() + 1
        self.current_day_weekend = self.current_weekday >= 6
        self.current_day = self.time_in_year("days")
        return

    def time_in_year(self, unit="timesteps", from_init=False):
        """
        Time passed since the beginning of the year.

        Parameters
        ----------
        unit : str, optional
            Specifies the unit for the result.

            - 'timesteps' Return the time as timesteps.
            - 'seconds' Return the time as seconds.
            - 'days' Return the time as days.
        from_init : bool, optional
            Time for init date or current date.

        Returns
        -------
        int :
            Time in specified unit.
        """
        dt0 = datetime.datetime(self._dt.year, 1, 1)
        if from_init:
            dt1 = self._init_dt
        else:
            dt1 = self._dt
        seconds = (dt1 - dt0).total_seconds()
        if unit == "timesteps":
            a, b = divmod(seconds, self.time_discretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`time_discretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds

    def time_in_week(self, unit="timesteps", from_init=False):
        """
        Time passed since beginning of the day.

        Parameters
        ----------
        unit : str, optional
            Specifies the unit for the result.

            - 'timesteps' Return the time as timesteps.
            - 'seconds' Return the time as seconds.
            - 'days' Return the time as days.
        from_init : bool, optional
            Time for init datetime or current datetime.

        Returns
        -------
        int :
            Time in specified unit.
        """
        if from_init:
            dt1 = self._init_dt
        else:
            dt1 = self._dt
        dt0 = datetime.datetime(dt1.year, dt1.month, dt1.day)
        dt0 -= datetime.timedelta(days=dt0.weekday())
        seconds = (dt1 - dt0).total_seconds()
        if unit == "timesteps":
            a, b = divmod(seconds, self.time_discretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`time_discretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds

    def time_in_day(self, unit="timesteps", from_init=False):
        """
        Time passed since beginning of the day.

        Parameters
        ----------
        unit : str, optional
            Specifies the unit for the result.

            - 'timesteps' Return the time as timesteps.
            - 'seconds' Return the time as seconds.
            - 'days' Return the time as days.
        from_init : bool, optional
            Time for init datetime or current datetime.

        Returns
        -------
        int :
            Time in specified unit.
        """
        if from_init:
            dt1 = self._init_dt
        else:
            dt1 = self._dt
        dt0 = datetime.datetime(dt1.year, dt1.month, dt1.day)
        seconds = (dt1 - dt0).total_seconds()
        if unit == "timesteps":
            a, b = divmod(seconds, self.time_discretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`time_discretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds
