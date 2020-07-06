import os.path as op
import numpy as np
from pycity_scheduling.classes import *

__all__ = [
    "schedule_to_csv",
    "ref_schedule_to_csv",
]


def schedule_to_csv(input_list, file_name, schedule=None):
    """Write the optimized schedule of all entities to a csv file.

    MDI: but where do all the optimized entities come from?

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str
        Specify the file name.
    schedule : str, optional
           Schedule to save.
           `None` : Current schedule
           'default' : Normal schedule
           'Ref', 'reference' : Reference schedule
    """
    sub_schedules = []
    headers = []

    for ent in input_list:
        if schedule is None:
            schedule = ent.current_schedule
        for name, sub_schedule in ent.schedules[schedule].items():
            headers.append(str(ent) + "_" + name)
            sub_schedules.append(sub_schedule)
    v = np.array(sub_schedules)
    p = op.join(op.dirname(op.dirname(op.dirname(__file__))), "output",
                "{0:s}.csv".format(file_name))
    np.savetxt(p, v.transpose(),
               delimiter="\t", fmt="%8.6f", header="\t".join(headers), comments="")


def ref_schedule_to_csv(input_list, file_name):
    """Write the reference schedule of all entities to a csv file.

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str
        Specify the file name.
    """
    import warnings
    warnings.warn("ref_schedule_to_csv() is deprecated; use schedule_to_csv() instead", DeprecationWarning)
    schedule_to_csv(input_list, file_name, schedule="Ref")
