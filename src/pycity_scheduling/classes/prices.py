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
import os.path as op
import calendar
import warnings
import pycity_base.classes.prices as pr


class Prices(pr.Prices):
    """
    Extension of pyCity_base class Prices for scheduling purposes.

    Parameters
    ----------
    timer : Timer
        Timer instance for generating needed prices.
    da_prices : array_like, optional
        Day-ahead prices for each timestep in the `simu_horizon`
        in [ct/kWh].
    tou_prices : array_like, optional
        Time-of-use prices for each timestep in the `simu_horizon`
        in [ct/kWh].
    co2_prices : array_like, optional
        CO2 emissions for each timestep in the `simu_horizon` in [g/kWh].
    feedin_factor : float, optional
        Factor which is multiplied to the prices for feed-in revenue.
        Should be in [0,1], as prices for feed-in are usually lower than
        for consumption.

    Notes
    -----
    - If prices are loaded automatically, the simulation period must lie within a single year.

    - CO2 emissions and day-ahead prices are currently available for the year 2015 only.
    """

    da_price_cache = None
    tou_price_cache = None
    tou_price_cache_year = None
    co2_price_cache = None

    def __init__(self, timer, da_prices=None,
                 tou_prices=None, co2_prices=None, feedin_factor=0):
        super(Prices, self).__init__()

        root_dir = op.dirname(op.dirname(__file__))
        timesteps = timer.time_in_year()
        factor = 900 / timer.time_discretization

        if da_prices is None:
            if self.da_price_cache is None:
                file_name = "da_prices_quarter-hour_2015.txt"
                file_path = op.join(root_dir, "data", file_name)
                tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
                tmp /= 10  # convert [Eur/MWh] to [ct/kWh]
                Prices.da_price_cache = tmp
            self.da_prices = self._interp_prices(Prices.da_price_cache,
                                                 timesteps,
                                                 timer.simu_horizon,
                                                 factor,
                                                 'step')
        else:
            if len(da_prices) != timer.simu_horizon:
                raise ValueError(
                    "Provided day-ahead price data do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(da_prices))
                )
            self.da_prices = np.array(da_prices)

        if tou_prices is None:
            if Prices.tou_price_cache_year != timer.year:
                summer_weekday_prices = np.array(
                    [7.7]*28 + [11.4]*16 + [14]*24 + [11.4]*8 + [7.7]*20
                )
                winter_weekday_prices = np.array(
                    [7.7]*28 + [14]*16 + [11.4]*24 + [14]*8 + [7.7]*20
                )
                weekend_prices = np.array([8.7] * 96)
                winter_week = np.concatenate((
                    np.tile(winter_weekday_prices, 5),
                    np.tile(weekend_prices, 2)
                ))
                summer_week = np.concatenate((
                    np.tile(summer_weekday_prices, 5),
                    np.tile(weekend_prices, 2)
                ))
                days_to_summer = 120 * 96
                if timer.is_leap:
                    days_to_summer += 96
                wd = calendar.weekday(timer.year, 1, 1) * 96
                winter_prices = np.tile(winter_week, 19)[wd:wd+days_to_summer]
                wd = calendar.weekday(timer.year, 5, 1) * 96
                summer_prices = np.tile(summer_week, 28)[wd:wd+184*96]
                wd = calendar.weekday(timer.year, 11, 1) * 96
                winter_prices2 = np.tile(winter_week, 15)[wd:wd+61*96]
                tou_prices = np.concatenate(
                    (winter_prices, summer_prices, winter_prices2)
                )
                tou_avg = 9.5
                file_name = "consumer_prices_yearly.txt"
                file_path = op.join(root_dir, "data", file_name)
                tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
                if len(tmp) <= timer.year - 2000:
                    warnings.warn("Year {} not in `consumer_prices_yearly.txt`. Using year {} instead."
                                  .format(timer.year, 2000+len(tmp)-1))
                    avg_price = tmp[-1]
                else:
                    avg_price = tmp[timer.year - 2000]
                Prices.tou_price_cache = tou_prices / tou_avg * avg_price
                Prices.tou_price_cache_year = timer.year
            self.tou_prices = self._interp_prices(Prices.tou_price_cache,
                                                  timesteps,
                                                  timer.simu_horizon,
                                                  factor,
                                                  'step')
        else:
            if len(tou_prices) != timer.simu_horizon:
                raise ValueError(
                    "Provided Time Of Use prices do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(tou_prices))
                )
            self.tou_prices = np.array(tou_prices)

        if co2_prices is None:
            if self.co2_price_cache is None:
                file_name = "co2_emissions_quarter-hour_2015.txt"
                file_path = op.join(root_dir, "data", file_name)
                tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
                Prices.co2_price_cache = tmp
            self.co2_prices = self._interp_prices(Prices.co2_price_cache,
                                                  timesteps,
                                                  timer.simu_horizon,
                                                  factor,
                                                  'step')
        else:
            if len(co2_prices) != timer.simu_horizon:
                raise ValueError(
                    "Provided CO2 price data do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(co2_prices))
                )
            self.co2_prices = np.array(co2_prices)

        self.feedin_factor = feedin_factor

    @staticmethod
    def _interp_prices(prices, timesteps, length, factor=1, mode='linear'):
        """
        Interpolate and slice prices.

        Interpolates a price vector to the correct resolution and then extracts
        the specified range from it.

        Parameters
        ----------
        prices : array_like
            Original prices. Is not modified by the function.
        timesteps : int
            First timestep in the interpolated prices.
        length : int
            Number of timesteps in the interpolated prices.
        factor : float, optional
            Factor by which the original prices are interpolated.
        mode : str, optional
            Must be 'linear' or 'step'.
            'linear' : linear interpolation
            'step' : view original prices as step function

        Returns
        -------
        numpy.ndarray :
            Interpolated prices.
        """
        if factor != 1:
            old_len = len(prices)
            new_len = int(old_len * factor)
            if mode == 'linear':
                prices = np.interp(range(new_len), range(old_len), prices)
            elif mode == 'step':
                if factor > 1:
                    factor = int(factor)
                    prices = np.array([np.repeat(p, factor) for p in prices])
                    np.reshape(prices, new_len)
                else:
                    factor = int(1/factor)
                    prices = prices[::factor].copy()
            else:
                raise ValueError("Mode {} is invalid.".format(mode))
        interp_prices = prices[timesteps:timesteps+length].copy()
        return interp_prices
