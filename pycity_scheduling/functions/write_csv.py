import os.path as op
import numpy as np
from pycity_scheduling.classes import *

__all__ = [
    "schedule_to_csv",
    "ref_schedule_to_csv",
]


def schedule_to_csv(input_list, file_name):
    """Write the optimized schedule of all entities to a csv file.

    MDI: but where do all the optimized entities come from?

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str
        Specify the file name.
    """
    l = []
    for ent in input_list:
        if isinstance(ent, BatteryEntity):
            l.append(ent.P_El_Schedule)
            l.append(ent.E_El_Schedule)
        elif isinstance(ent, ElectricalEntity):
            l.append(ent.P_El_Schedule)
        elif isinstance(ent, ThermalEnergyStorage):
            l.append(ent.P_Th_Schedule)
            l.append(ent.E_Th_Schedule)
        elif isinstance(ent, ThermalEntity):
            l.append(ent.P_Th_Schedule)
    v = np.array(l)
    n = ""
    for ent in input_list:
        n += str(ent) + "\t"
        if isinstance(ent, ThermalEnergyStorage):
            n += str(ent) + " Stor\t"
        if isinstance(ent, BatteryEntity):
            n += str(ent) + " Stor\t"
    p = op.join(op.dirname(op.dirname(op.dirname(__file__))), "output",
                "{0:s}.csv".format(file_name))
    np.savetxt(p, v.transpose(),
               delimiter="\t", fmt="%8.6f", header=n, comments="")


def ref_schedule_to_csv(input_list, file_name):
    """Write the reference schedule of all entities to a csv file.

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str
        Specify the file name.
    """
    l = []
    for ent in input_list:
        if isinstance(ent, BatteryEntity):
            l.append(ent.P_El_Ref_Schedule)
            l.append(ent.E_El_Ref_Schedule)
        elif isinstance(ent, ElectricalEntity):
            l.append(ent.P_El_Ref_Schedule)
        elif isinstance(ent, ThermalEnergyStorage):
            l.append(ent.P_Th_Ref_Schedule)
            l.append(ent.E_Th_Ref_Schedule)
        elif isinstance(ent, ThermalEntity):
            l.append(ent.P_Th_Ref_Schedule)
    v = np.array(l)
    n = ""
    for ent in input_list:
        n += str(ent) + "\t"
        if isinstance(ent, ThermalEnergyStorage):
            n += str(ent) + " Stor\t"
        if isinstance(ent, BatteryEntity):
            n += str(ent) + " Stor\t"
    p = op.join(op.dirname(op.dirname(op.dirname(__file__))), "output",
                "{0:s}.csv".format(file_name))
    np.savetxt(p, v.transpose(),
               delimiter="\t", fmt="%8.6f", header=n, comments="")
