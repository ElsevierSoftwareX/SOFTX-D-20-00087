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
import pycity_base.classes.demand.electrical_demand as ed

from pycity_scheduling.classes.electrical_entity import ElectricalEntity


class FixedLoad(ElectricalEntity, ed.ElectricalDemand):
    """
    Extension of pyCity_base class ElectricalDemand for scheduling purposes.

    As for all uncontrollable loads, the `p_el_schedule` contains the forecast
    of the load.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    method : int, optional
        Defaults to method zero.

        - 0 : provide load curve directly
        - 1 : standard load profile (for households)
        - 2 : stochastic electrical load model
        - 3 : annual profile based on measured weekly profiles (non-residential)
        - 4 : annual profile based on measured annual profiles (non-residential)
    demand : numpy.ndarray, optional
        Demand for all investigated time steps in [kW] when using `method=0`.
    annual_demand : float, optional
        Required for SLP and recommended for method 2.
        Defines the annual electrical demand in [kWh].
        If method 2 is chosen but no value is given, a standard value for
        Germany (https://lena.sachsen-anhalt.de/fileadmin/Bibliothek/Sonstige_Webprojekte/Lena/Pressemitteilungen/
        Stromspiegel/Stromspiegel2014_Medienblatt.pdf, accessed on 2020/09/28) is used.
    profile_type : str, optional
        - H0 : Household
        - L0 : Farms
        - L1 : Farms with breeding / cattle
        - L2 : Farms without cattle
        - G0 : Business (general)
        - G1 : Business (workingdays 8:00 AM - 6:00 PM)
        - G2 : Business with high loads in the evening
        - G3 : Business (24 hours)
        - G4 : Shops / Barbers
        - G5 : Bakery
        - G6 : Weekend operation
    total_nb_occupants : int, optional
        Number of people living in the household for `method=2`.
    randomize_appliances : bool, optional
        Randomization of appliances for `method=2`. Defaults to `True`.

        - True : distribute installed appliances randomly
        - False : use the standard distribution
    light_configuration : int, optional
        There are 100 light bulb configurations predefined for the
        stochastic model when using `method=2`. Defaults to zero.
        A value between 0 and 100 should be provided.
    occupancy : int, optional
        Occupancy given at 10-minute intervals for a full year for `method=2`.
    do_normalization : bool, optional
        Defines, if stochastic profile (`method=2`) should be
        normalized to given annual_demand value. Defaults to `False`.
        If set to `False`, annual el. demand depends on stochastic el. load
        profile generation. If set to `True`, does normalization with
        annual_demand.
    method_3_type : str, optional
        Defines type of profile for method=3. Defaults to `None`.
        Options:

        - 'food_pro': Food production
        - 'metal': Metal company
        - 'rest': Restaurant (with large cooling load)
        - 'sports': Sports hall
        - 'repair': Repair / metal shop
    method_4_type : str, optional
        Defines type of profile for method=4. Defaults to `None`.

        - 'metal_1' : Metal company with smooth profile
        - 'metal_2' : Metal company with fluctuation in profile
        - 'warehouse' : Warehouse
    prev_heat_dev : bool, optional
        Defines, if heating devices should be prevented within chosen
        appliances for `method=2`. Defaults to `False`.
        If set to True, DESWH, E-INST, Electric shower, Storage heaters
        and Other electric space heating are set to zero.
    app_filename : str, optional
        Path to Appliances file for `method=2`. Defaults to `None`.
        If set to None, uses default file Appliances.csv in
        /inputs/stochastic_electrical_load/.
    light_filename : str, optional
        Path to Lighting configuration file for `method=2`. Defaults to `None`.
        If set to None, uses default file Appliances.csv in
        /inputs/stochastic_electrical_load/.
    season_light_mod : bool, optional
        Defines, if cosine-wave should be used to strengthen seasonal
        influence on lighting. Defaults to `False`.
        If True, enlarges lighting power demand in winter month and reduces
        lighting power demand in summer month.
    light_mod_fac : float, optional
        Define factor, related to maximal lighting power, which is used
        to implement seasonal influence. Defaults to 25%.
        Only relevant, if `season_light_mod` == True

    Notes
    -----
    - Standard load profiles, for instance for Germany, can be found here:
      https://www.bdew.de/energie/standardlastprofile-strom/ (accessed on 2020/09/28)

    - Average German electricity consumption data per household can be found here:
      https://lena.sachsen-anhalt.de/fileadmin/Bibliothek/Sonstige_Webprojekte/Lena/Pressemitteilungen/
      Stromspiegel/Stromspiegel2014_Medienblatt.pdf (accessed on 2020/09/28)

    - The following constraint is added for removing the bounds from EE:

    .. math::
        p_{el} = load\\_curve
    """

    def __init__(self, environment, method=0, demand=0, annual_demand=0, profile_type="H0", single_family_house=True,
                 total_nb_occupants=0, randomize_appliances=True, light_configuration=0, occupancy=None,
                 do_normalization=False, method_3_type=None, method_4_type=None, prev_heat_dev=False, app_filename=None,
                 light_filename=None, season_light_mod=False, light_mod_fac=0.25):
        super().__init__(environment, method, demand*1000, annual_demand, profile_type, single_family_house,
                         total_nb_occupants, randomize_appliances, light_configuration, occupancy, do_normalization,
                         method_3_type, method_4_type, prev_heat_dev, app_filename, light_filename, season_light_mod,
                         light_mod_fac)
        self._long_id = "FL_" + self._id_string

        ts = self.timer.time_in_year(from_init=True)
        p = self.loadcurve[ts:ts+self.simu_horizon] / 1000
        self.p_el_schedule = p

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        for t in self.op_time_vec:
            m.p_el_vars[t].setlb(self.p_el_schedule[timestep + t])
            m.p_el_vars[t].setub(self.p_el_schedule[timestep + t])
        return

    def new_schedule(self, schedule):
        super().new_schedule(schedule)
        self.copy_schedule(schedule, "default", "p_el")
        return

    def update_schedule(self):
        pass

    def reset(self, schedule=None):
        pass
