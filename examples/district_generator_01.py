import pycity_scheduling.util.factory as factory
import pycity_scheduling.util.debug as debug

env = factory.generate_standard_environment()

# 20 single family houses
num_sfh = 20
# 50% SFH.2002, 30% SFH.2010, 20% SFH.2016
sfh_distribution = {
    'SFH.2002': 0.5,
    'SFH.2010': 0.3,
    'SFH.2016': 0.2,
}
# 50% with heat pump, 10% with boiler, 40% with electric heater
sfh_heating_distribution = {
    'HP': 0.5,
    'BL': 0.1,
    'EH': 0.4,
}
# all apartments have a fixed load, 20% have a deferrable load, 30% have an
# electric vehicle
#
# 50% of buildings have a battery, 80% have a photovoltaic plant
# These values are rounded in case they cannot be matched perfectly with the
sfh_device_probs = {
    'FL': 1,
    'DL': 0.2,
    'EV': 0.3,
    'BAT': 0.5,
    'PV': 0.8,
}
# 5 multi family houses, number of apartments comes from the tabula data
num_mfh = 5
mfh_distribution = {
    'MFH.2002': 0.6,
    'MFH.2010': 0.2,
    'MFH.2016': 0.2,
}
mfh_heating_distribution = {
    'HP': 0.4,
    'BL': 0.2,
    'EH': 0.4,
}
mfh_device_probs = {
    'FL': 1,
    'DL': 0.2,
    'EV': 0.2,
    'BAT': 0.4,
    'PV': 0.8,
}
district = factory.generate_tabula_district(env, num_sfh, num_mfh,
                                            sfh_distribution,
                                            sfh_heating_distribution,
                                            sfh_device_probs,
                                            mfh_distribution,
                                            mfh_heating_distribution,
                                            mfh_device_probs)

# Hierachically print the district and all houses
debug.print_district(district, 1)
