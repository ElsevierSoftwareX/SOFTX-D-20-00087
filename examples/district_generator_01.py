import pycity_scheduling.util.factory as factory

env = factory.generate_standard_environment()

num_sfh = 20
sfh_distribution = {
    'SFH.2002': 0.5,
    'SFH.2010': 0.3,
    'SFH.2016': 0.2,
}
sfh_heating_distribution = {
    'HP': 0.5,
    'BL': 0.1,
    'EH': 0.4,
}
sfh_device_probs = {
    'FL': 1,
    'DL': 0.2,
    'EV': 0.3,
    'BAT': 0.5,
    'PV': 0.8,
}
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
for nid, node in district.nodes.items():
    print(nid, node)
