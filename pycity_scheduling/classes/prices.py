import os
import calendar
import numpy as np
import scipy.ndimage.interpolation as intp
import pycity_base.classes.Prices as pr

from ..exception import PyCitySchedulingInitError
from .timer import Timer


class Prices(pr.Prices):
    """
    Extension of pycity class Prices for scheduling purposes.
    """

    def __init__(self, timer, da_prices=None,
                 tou_prices=None, co2_prices=None):
        """Initialize Prices.

        Parameters
        ----------
        timer : Timer
            Timer instance for generating needed prices.
        da_prices : array_like, optional
            Day-ahead prices for quarter-hour intervals in [ct/kWh].
        co2_prices : array_like, optional
            CO2 price like for quarter-hour intervals in [g/kWh].

        Notes
        -----
         - when prices are loaded automatically, simulation must stay within a
           single year
         - price data are only available for 2015 at the moment
        """
        super(Prices, self).__init__()

        timesteps = timer.time_in_year()

        if da_prices is None:
            root_dir = os.path.dirname(os.path.dirname(__file__))
            file_name = "da_prices_quarter-hour_2015.txt"
            file_path = os.path.join(root_dir, "data", file_name)
            tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
            if timer.timeDiscretization != 900:
                tmp = intp.zoom(
                    tmp,
                    31536000 / timer.timeDiscretization / 35040,
                )
            tmp /= 10  # convert [Eur/MWh] to [ct/kWh]
            self.da_prices = np.empty(timer.simu_horizon)
            np.copyto(
                self.da_prices,
                tmp[timesteps:timesteps+timer.simu_horizon]
            )
        else:
            if len(da_prices) != timer.simu_horizon:
                raise PyCitySchedulingInitError(
                    "Provided day-ahead price data do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(da_prices))
                )
            self.da_prices = np.array(da_prices)

        if tou_prices is None:
            root_dir = os.path.dirname(os.path.dirname(__file__))
            file_name = "consumer_prices_yearly.txt"
            file_path = os.path.join(root_dir, "data", file_name)
            tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
            year_index = timer.year - 2000
            avg_price = tmp[year_index]
            tou_avg = 9.5
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
            tou_prices = tou_prices / tou_avg * avg_price
            if timer.timeDiscretization != 900:
                tou_prices = np.interp(
                    range(31536000//timer.timeDiscretization),
                    range(35040),
                    tou_prices
                )
            self.tou_prices = np.empty(timer.simu_horizon)
            np.copyto(
                self.tou_prices,
                tou_prices[timesteps:timesteps+timer.simu_horizon]
            )
        else:
            if len(tou_prices) != timer.simu_horizon:
                raise PyCitySchedulingInitError(
                    "Provided Time Of Use prices do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(tou_prices))
                )
            self.tou_prices = np.array(tou_prices)

        if co2_prices is None:
            root_dir = os.path.dirname(os.path.dirname(__file__))
            file_name = "co2_emissions_quarter-hour_2015.txt"
            file_path = os.path.join(root_dir, "data", file_name)
            tmp = np.loadtxt(file_path, dtype=np.float32, skiprows=1)
            if timer.timeDiscretization != 900:
                tmp = np.interp(
                    range(31536000 // timer.timeDiscretization),
                    range(35040),
                    tmp
                )
            self.co2_prices = np.empty(timer.simu_horizon)
            np.copyto(
                self.co2_prices,
                tmp[timesteps:timesteps+timer.simu_horizon]
            )
        else:
            if len(co2_prices) != timer.simu_horizon:
                raise PyCitySchedulingInitError(
                    "Provided CO2 price data do not match the number of "
                    "timesteps in the simulation horizon.\n"
                    "Number of timesteps: {0}, Length of price data: {1}"
                    .format(timer.simu_horizon, len(co2_prices))
                )
            self.co2_prices = np.array(co2_prices)
