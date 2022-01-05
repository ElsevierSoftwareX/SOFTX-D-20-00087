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


"""
Dictionary with building data from TABULA Project
http://www.episcope.eu/ (accessed on 2020/09/28)
"""

tabula_building_data = dict()


# Single family houses:

tabula_building_data['DE.N.SFH.01.Gen'] = tabula_building_data['SFH.1200'] = {
    'building_type': 'DE.N.SFH.01.Gen',
    'construction_year': '1200-1859',
    'net_floor_area': 219.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 93.0,
    'th_profile_type': 'HEF',
    'roof_area': 134.2,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.02.Gen'] = tabula_building_data['SFH.1860'] = {
    'building_type': 'DE.N.SFH.02.Gen',
    'construction_year': '1860-1918',
    'net_floor_area': 142.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 95.9,
    'th_profile_type': 'HEF',
    'roof_area': 83.1,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.03.Gen'] = tabula_building_data['SFH.1919'] = {
    'building_type': 'DE.N.SFH.03.Gen',
    'construction_year': '1919-1948',
    'net_floor_area': 303.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 83.7,
    'th_profile_type': 'HEF',
    'roof_area': 214.0,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.04.Gen'] = tabula_building_data['SFH.1949'] = {
    'building_type': 'DE.N.SFH.04.Gen',
    'construction_year': '1949-1957',
    'net_floor_area': 111.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 111.5,
    'th_profile_type': 'HEF',
    'roof_area': 125.4,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.05.Gen'] = tabula_building_data['SFH.1958'] = {
    'building_type': 'DE.N.SFH.05.Gen',
    'construction_year': '1958-1968',
    'net_floor_area': 121.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 117.4,
    'th_profile_type': 'HEF',
    'roof_area': 168.9,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.06.Gen'] = tabula_building_data['SFH.1969'] = {
    'building_type': 'DE.N.SFH.06.Gen',
    'construction_year': '1969-1978',
    'net_floor_area': 173.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 90.4,
    'th_profile_type': 'HEF',
    'roof_area': 183.1,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.SFH.07.Gen'] = tabula_building_data['SFH.1979'] = {
    'building_type': 'DE.N.SFH.07.Gen',
    'construction_year': '1979-1983',
    'net_floor_area': 216.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 74.9,
    'th_profile_type': 'HEF',
    'roof_area': 100.8,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.08.Gen'] = tabula_building_data['SFH.1984'] = {
    'building_type': 'DE.N.SFH.08.Gen',
    'construction_year': '1984-1994',
    'net_floor_area': 150.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 94.4,
    'th_profile_type': 'HEF',
    'roof_area': 123.2,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.09.Gen'] = tabula_building_data['SFH.1995'] = {
    'building_type': 'DE.N.SFH.09.Gen',
    'construction_year': '1995-2001',
    'net_floor_area': 122.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 97.6,
    'th_profile_type': 'HEF',
    'roof_area': 115.5,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.10.Gen'] = tabula_building_data['SFH.2002'] = {
    'building_type': 'DE.N.SFH.10.Gen',
    'construction_year': '2002-2009',
    'net_floor_area': 147.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 72.9,
    'th_profile_type': 'HEF',
    'roof_area': 85.9,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.11.Gen'] = tabula_building_data['SFH.2010'] = {
    'building_type': 'DE.N.SFH.11.Gen',
    'construction_year': '2010-2015',
    'net_floor_area': 187.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 49.5,
    'th_profile_type': 'HEF',
    'roof_area': 131.9,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.SFH.12.Gen'] = tabula_building_data['SFH.2016'] = {
    'building_type': 'DE.N.SFH.12.Gen',
    'construction_year': '2016-...',
    'net_floor_area': 187.0,
    'apartments': 1,
    'el_demand': 4000.0,
    'el_profile_type': 'H0',
    'th_demand': 42.3,
    'th_profile_type': 'HEF',
    'roof_area': 131.9,
    'roof_angle': 30.0
}

# Multi family houses:

tabula_building_data['DE.N.MFH.01.Gen'] = tabula_building_data['MFH.1200'] = {
    'building_type': 'DE.N.MFH.01.Gen',
    'construction_year': '1200-1859',
    'net_floor_area': 677.0,
    'apartments': 5,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 98.3,
    'th_profile_type': 'HMF',
    'roof_area': 284.1,
    'roof_angle': 22.0
}

tabula_building_data['DE.N.MFH.02.Gen'] = tabula_building_data['MFH.1860'] = {
    'building_type': 'DE.N.MFH.02.Gen',
    'construction_year': '1860-1918',
    'net_floor_area': 312.0,
    'apartments': 4,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 80.5,
    'th_profile_type': 'HMF',
    'roof_area': 102.8,
    'roof_angle': 22.0
}

tabula_building_data['DE.N.MFH.03.Gen'] = tabula_building_data['MFH.1919'] = {
    'building_type': 'DE.N.MFH.03.Gen',
    'construction_year': '1919-1948',
    'net_floor_area': 385.0,
    'apartments': 2,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 82.5,
    'th_profile_type': 'HMF',
    'roof_area': 158.5,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.MFH.04.Gen'] = tabula_building_data['MFH.1949'] = {
    'building_type': 'DE.N.MFH.04.Gen',
    'construction_year': '1949-1957',
    'net_floor_area': 632.0,
    'apartments': 9,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 79.3,
    'th_profile_type': 'HMF',
    'roof_area': 355.0,
    'roof_angle': 22.0
}

tabula_building_data['DE.N.MFH.05.Gen'] = tabula_building_data['MFH.1958'] = {
    'building_type': 'DE.N.MFH.05.Gen',
    'construction_year': '1958-1968',
    'net_floor_area': 3129.0,
    'apartments': 32,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 147.2,
    'th_profile_type': 'HMF',
    'roof_area': 971.1,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.MFH.06.Gen'] = tabula_building_data['MFH.1969'] = {
    'building_type': 'DE.N.MFH.06.Gen',
    'construction_year': '1969-1978',
    'net_floor_area': 469.0,
    'apartments': 8,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 74.0,
    'th_profile_type': 'HMF',
    'roof_area': 216.7,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.MFH.07.Gen'] = tabula_building_data['MFH.1979'] = {
    'building_type': 'DE.N.MFH.07.Gen',
    'construction_year': '1979-1983',
    'net_floor_area': 654.0,
    'apartments': 9,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 68.6,
    'th_profile_type': 'HMF',
    'roof_area': 248.3,
    'roof_angle': 30.0
}

tabula_building_data['DE.N.MFH.08.Gen'] = tabula_building_data['MFH.1984'] = {
    'building_type': 'DE.N.MFH.08.Gen',
    'construction_year': '1984-1994',
    'net_floor_area': 778.0,
    'apartments': 10,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 72.6,
    'th_profile_type': 'HMF',
    'roof_area': 249.4,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.MFH.09.Gen'] = tabula_building_data['MFH.1995'] = {
    'building_type': 'DE.N.MFH.09.Gen',
    'construction_year': '1995-2001',
    'net_floor_area': 835.0,
    'apartments': 12,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 68.8,
    'th_profile_type': 'HMF',
    'roof_area': 283.7,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.MFH.10.Gen'] = tabula_building_data['MFH.2002'] = {
    'building_type': 'DE.N.MFH.10.Gen',
    'construction_year': '2002-2009',
    'net_floor_area': 2190.0,
    'apartments': 19,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 54.0,
    'th_profile_type': 'HMF',
    'roof_area': 580.0,
    'roof_angle': 22.0
}

tabula_building_data['DE.N.MFH.11.Gen'] = tabula_building_data['MFH.2010'] = {
    'building_type': 'DE.N.MFH.11.Gen',
    'construction_year': '2010-2015',
    'net_floor_area': 1305.0,
    'apartments': 17,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 47.7,
    'th_profile_type': 'HMF',
    'roof_area': 321.1,
    'roof_angle': 0.0
}

tabula_building_data['DE.N.MFH.12.Gen'] = tabula_building_data['MFH.2016'] = {
    'building_type': 'DE.N.MFH.12.Gen',
    'construction_year': '2016-...',
    'net_floor_area': 1305.0,
    'apartments': 17,
    'el_demand': 3000.0,
    'el_profile_type': 'H0',
    'th_demand': 28.1,
    'th_profile_type': 'HMF',
    'roof_area': 321.1,
    'roof_angle': 0.0
}
