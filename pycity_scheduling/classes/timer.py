import datetime
import calendar
import pycity_base.classes.Timer as ti


class Timer(ti.Timer):
    """
    Extension of pycity class Timer for scheduling purposes

    Notes
    -----
     - This class' behaviour may differ from the one of the baseclass, as it
       keeps an actual date rather than a relative counter only
    """

    def __init__(self, step_size=900, op_horizon=96,
                 mpc_horizon=None, mpc_step_width=None,
                 initial_date=(2015, 1, 1), initial_time=(0, 0, 0)):
        """Initialize Timer.

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
        """
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
                "`timeDiscretization`."
            )
        # Workaround to make the weather instance calculate values for a whole
        # year.
        horizon = int(365 * 24 * 3600 / step_size)
        # if calendar.isleap(initial_date[0]):
        #     horizon += 24 * 3600 / step_size
        super(Timer, self).__init__(timeDiscretization=step_size,
                                    timestepsUsedHorizon=op_horizon,
                                    timestepsHorizon=horizon,
                                    timestepsTotal=horizon,
                                    initialDay=initial_day)

        self.time_slot = step_size / 3600
        self._init_dt = self._dt
        if mpc_horizon is None:
            self.simu_horizon = op_horizon
        else:
            self.simu_horizon = mpc_horizon
        if mpc_step_width is None:
            self.mpc_step_width = op_horizon
        else:
            self.mpc_step_width = mpc_step_width

    @property
    def datetime(self):
        return self._dt

    @property
    def date(self):
        return datetime.date(self._dt.year, self._dt.month, self._dt.day)

    @property
    def is_leap(self):
        return calendar.isleap(self._dt.year)

    @property
    def year(self):
        return self._dt.year

    @property
    def month(self):
        return self._dt.month

    @property
    def day(self):
        return self._dt.day

    @property
    def weekday(self):
        return self._dt.weekday()

    @property
    def time(self):
        return datetime.time(self._dt.hour, self._dt.minute, self._dt.second)

    @property
    def hour(self):
        return self._dt.hour

    @property
    def minute(self):
        return self._dt.minute

    @property
    def second(self):
        return self._dt.second

    def print_datetime(self):
        return str(self._dt)

    def mpc_update(self):
        """Update Timer for MPC.

        Move `self.mpc_step_width` timesteps forward.
        """
        self.currentTimestep += self.mpc_step_width
        self._dt += datetime.timedelta(
            seconds=self.timeDiscretization*self.mpc_step_width
        )

        # update values from parent class
        self.currentOptimizationPeriod += 1
        self.currentWeekday = self._dt.weekday() + 1
        self.currentDayWeekend = self.currentWeekday >= 6
        self.currentDay = self.time_in_year("days")

    def op_update(self):
        """Update Timer for a normal scheduling optimization.

        Go `self.timestepsUsedHorizon` timesteps forward.
        """
        self.currentTimestep += self.timestepsUsedHorizon
        self._dt += datetime.timedelta(
            seconds=self.timeDiscretization*self.timestepsUsedHorizon
        )

        # update values from parent class
        self.currentOptimizationPeriod += 1
        self.currentWeekday = self._dt.weekday() + 1
        self.currentDayWeekend = self.currentWeekday >= 6
        self.currentDay = self.time_in_year("days")

    def reset(self):
        """Reset the Timer to the initial state."""
        self._dt = self._init_dt
        self.currentTimestep = 0
        self.currentOptimizationPeriod = 0
        self.currentWeekday = self._dt.weekday() + 1
        self.currentDayWeekend = self.currentWeekday >= 6
        self.currentDay = self.time_in_year("days")

    def time_in_year(self, unit="timesteps", from_init=False):
        """Time passed since the beginning of the year.

        Parameters
        ----------
        unit : {"timesteps", "seconds", "days}, optional
            Specifies the unit for the result.
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
            a, b = divmod(seconds, self.timeDiscretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`timeDiscretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds

    def time_in_week(self, unit="timesteps", from_init=False):
        """Time passed since beginning of the day.

        Parameters
        ----------
        unit : {"timesteps", "seconds", "days}, optional
            Specifies the unit for the result.
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
            a, b = divmod(seconds, self.timeDiscretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`timeDiscretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds

    def time_in_day(self, unit="timesteps", from_init=False):
        """Time passed since beginning of the day.

        Parameters
        ----------
        unit : {"timesteps", "seconds", "days}, optional
            Specifies the unit for the result.
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
            a, b = divmod(seconds, self.timeDiscretization)
            if b > 0:
                raise ValueError(
                    "The difference from the starting point of the simulation "
                    "to the beginning of the year must be a multiple of "
                    "`timeDiscretization`."
                )
            return int(a)
        elif unit == "days":
            return seconds // 86400
        else:
            return seconds
