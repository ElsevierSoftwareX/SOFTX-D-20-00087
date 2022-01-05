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
Dictionary with electrical vehicle data from German ADAC e.V.:
https://www.adac.de/rund-ums-fahrzeug/autokatalog/ (accessed on 2020/09/28)
"""

ev_data = dict()


ev_data['EV.01'] = {'name': 'BMW i3',
                    'charging_method': 'standard',
                    'p_el_nom': 2.68,
                    'e_el_storage_max': 22.0,
                    'soc_max': 1.0
                    }

ev_data['EV.02'] = {'name': 'BMW i3',
                    'charging_method': 'fast',
                    'p_el_nom': 37.6,
                    'e_el_storage_max': 22.0,
                    'soc_max': 0.8
                    }

ev_data['EV.03'] = {'name': 'Ford Focus',
                    'charging_method': 'standard',
                    'p_el_nom': 2.01,
                    'e_el_storage_max': 23.0,
                    'soc_max': 1.0
                    }

ev_data['EV.04'] = {'name': 'Ford Focus',
                    'charging_method': 'fast',
                    'p_el_nom': 3.29,
                    'e_el_storage_max': 23.0,
                    'soc_max': 1.0
                    }

ev_data['EV.05'] = {'name': 'Renault ZOE',
                    'charging_method': 'standard',
                    'p_el_nom': 2.3,
                    'e_el_storage_max': 22,
                    'soc_max': 1.0
                    }

ev_data['EV.06'] = {'name': 'Mercedes SLS',
                    'charging_method': 'fast',
                    'p_el_nom': 20.0,
                    'e_el_storage_max': 60.0,
                    'soc_max': 0.9
                    }

ev_data['EV.07'] = {'name': 'Nissan Leaf',
                    'charging_method': 'standard',
                    'p_el_nom': 3.0,
                    'e_el_storage_max': 24.0,
                    'soc_max': 1.0
                    }

ev_data['EV.08'] = {'name': 'Nissan Leaf',
                    'charging_method': 'fast',
                    'p_el_nom': 48.0,
                    'e_el_storage_max': 24.0,
                    'soc_max': 0.8
                    }

ev_data['EV.09'] = {'name': 'Renault Twizy',
                    'charging_method': 'standard',
                    'p_el_nom': 1.743,
                    'e_el_storage_max': 6.1,
                    'soc_max': 1.0
                    }

ev_data['EV.10'] = {'name': 'Renault Twizy',
                    'charging_method': 'fast',
                    'p_el_nom': 2.44,
                    'e_el_storage_max': 6.1,
                    'soc_max': 1.0
                    }

ev_data['EV.11'] = {'name': 'Renault Kangoo',
                    'charging_method': 'standard',
                    'p_el_nom': 2.75,
                    'e_el_storage_max': 22.0,
                    'soc_max': 1.0
                    }

ev_data['EV.12'] = {'name': 'Renault Kangoo',
                    'charging_method': 'fast',
                    'p_el_nom': 3.667,
                    'e_el_storage_max': 22.0,
                    'soc_max': 1.0
                    }

ev_data['EV.13'] = {'name': 'VW e-up!',
                    'charging_method': 'standard',
                    'p_el_nom': 2.88,
                    'e_el_storage_max': 18.7,
                    'soc_max': 1.0
                    }

ev_data['EV.14'] = {'name': 'VW e-up!',
                    'charging_method': 'fast',
                    'p_el_nom': 37.4,
                    'e_el_storage_max': 18.7,
                    'soc_max': 0.8
                    }

ev_data['EV.15'] = {'name': 'Tesla Roadster',
                    'charging_method': 'standard',
                    'p_el_nom': 14.0,
                    'e_el_storage_max': 56.0,
                    'soc_max': 1.0
                    }

ev_data['EV.16'] = {'name': 'Smart fortwo electric',
                    'charging_method': 'standard',
                    'p_el_nom': 2.515,
                    'e_el_storage_max': 17.6,
                    'soc_max': 1.0
                    }

ev_data['EV.17'] = {'name': 'Smart fortwo electric',
                    'charging_method': 'fast',
                    'p_el_nom': 17.6,
                    'e_el_storage_max': 17.6,
                    'soc_max': 0.9
                    }
