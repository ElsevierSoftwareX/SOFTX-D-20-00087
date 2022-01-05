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

import pycity_scheduling.util.factory as factory
from pycity_scheduling.util import calculate_flexibility_potential


# This example shows how to quantify the operational flexibility potential for a given city district using
# pycity_scheduling. It is built upon the same district setup as defined in example 'example_12_district_generator.py'.


def main(do_plot=False):
    print("\n\n------ Example 14: District Flexibility Quantification ------\n\n")

    # First, create an environment using the factory's "generate_standard_environment" method. The environment
    # automatically encapsulates time, weather, and price data/information.
    env = factory.generate_standard_environment(initial_date=(2018, 12, 6), step_size=900, op_horizon=96)

    # Create 12 single-family houses:
    num_sfh = 12

    # 50% SFH.2002, 30% SFH.2010, 20% SFH.2016 (based on TABULA):
    sfh_distribution = {
        'SFH.2002': 0.5,
        'SFH.2010': 0.3,
        'SFH.2016': 0.2,
    }

    # 50% of the single-family houses are equipped with heat pump, 10% with boiler, and 40% with electrical heater:
    sfh_heating_distribution = {
        'HP': 0.5,
        'BL': 0.1,
        'EH': 0.4,
    }

    # All single-family houses are equipped with a fixed load, 20% have a deferrable load, and 30% have an electric
    # vehicle. Moreover, 50% of all single-family houses have a battery unit and 80% have a rooftop photovoltaic unit
    # installation.
    # The values are rounded in case they cannot be perfectly matched to the given number of buildings.
    sfh_device_probs = {
        'FL': 1.0,
        'DL': 0.2,
        'EV': 0.3,
        'BAT': 0.5,
        'PV': 0.8,
    }

    # Create 3 multi-family houses (number of apartments according to TABULA):
    num_mfh = 3

    # 60% MFH.2002, 20% SFH.2010, 20% SFH.2016 (based on TABULA):
    mfh_distribution = {
        'MFH.2002': 0.6,
        'MFH.2010': 0.2,
        'MFH.2016': 0.2,
    }

    # 40% of the multi-family houses are equipped with heat pump, 20% with boiler, and 40% with electrical heater:
    mfh_heating_distribution = {
        'HP': 0.4,
        'BL': 0.2,
        'EH': 0.4,
    }

    # All apartments inside a multi-family houses are equipped with a fixed load, 20% have a deferrable load, and 20%
    # have an electric vehicle. Moreover, 40% of all multi-family houses have a battery unit and 80% have a rooftop
    # photovoltaic unit installation.
    # The values are rounded in case they cannot be perfectly matched to the given number of buildings.
    mfh_device_probs = {
        'FL': 1.0,
        'DL': 0.2,
        'EV': 0.2,
        'BAT': 0.4,
        'PV': 0.8,
    }

    # Finally, create the desired city district using the factory's "generate_tabula_district" method:
    district = factory.generate_tabula_district(environment=env,
                                                number_sfh=num_sfh,
                                                number_mfh=num_mfh,
                                                sfh_building_distribution=sfh_distribution,
                                                sfh_heating_distribution=sfh_heating_distribution,
                                                sfh_device_probabilities=sfh_device_probs,
                                                mfh_building_distribution=mfh_distribution,
                                                mfh_heating_distribution=mfh_heating_distribution,
                                                mfh_device_probabilities=mfh_device_probs)


    # The city district's maximum operational flexibility potential in terms of the absolute flexibility gain metric can
    # be quantified very easily using the pycity_scheduling's "calculate_flexibility_potential" function. The absolute
    # flexibility gain is a measure for the energy shifted between a coordinated and an uncoordinated scheduling
    # scenario. Here, the coordinated case is represented through the central optimization algorithm, whereas the
    # uncoordinated case is represented through the stand-alone optimization algorithm.
    flex = calculate_flexibility_potential(city_district=district,
                                           algorithm="central",
                                           reference_algorithm="stand-alone")

    # Print the flexibility metric result:
    np.set_printoptions(formatter={'float': '{: >8.3f}'.format})
    print('Absolute flex. gain (kWh):    {: >8.3f}'.format(flex))
    return


# Conclusions:
# In the given scenario, the absolute flexibility gain within the city district scenario is about 754kWh for the defined
# day (24h). This means that up to this volume of energy can be shifted because of the local flexibility potentials.
# For example, this flexibility potential can be used to achieve several system level services such as peak-shaving.
# The quantification of the flexibility potential is usually a crucial task when it comes to the initial assessment of
# local energy systems and/or city district energy systems.


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
