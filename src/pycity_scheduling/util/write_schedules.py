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
import csv
import json


__all__ = [
    'schedule_to_dict',
    'schedule_to_csv',
    'schedule_to_json',
]


def schedule_to_dict(input_list, schedule=None):
    """
    Create a dictionary containing a reference to the optimized schedules.

    Parameters
    ----------
    input_list : list
        List of entities.
    schedule : str or list, optional
           Schedule or list of schedules to save.

           - `None` : Current schedule of entity
           - 'default' : Normal schedule
           - 'ref' : Reference schedule
    """
    if isinstance(schedule, str) or schedule is None:
        schedules = [schedule]
    elif isinstance(schedule, list):
        schedules = schedule
    else:
        raise ValueError("Unknown type for schedule argument.")
    entities = {str(entity): {} for entity in input_list}
    for ent, ent_schedules in zip(input_list, entities.values()):
        for schedule in schedules:
            if schedule is None:
                schedule = ent.current_schedule_active

            sub_schedules = ent.schedules[schedule].copy()
            ent_schedules[schedule] = sub_schedules
    return entities


def schedule_to_json(input_list, file_name, schedule=None):
    """
    Write the optimized schedule of all entities to a json file.

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str or file-like object
        Specify the file name or an open file where the json should be saved
        in. If file_name is a string and it does not have the `.json`
        extension it will be appended.
    schedule : str or list, optional
           Schedule or list of schedules to save.

           - `None` : Current schedule of entity
           - 'default' : Normal schedule
           - 'ref' : Reference schedule
    """
    entities = schedule_to_dict(input_list, schedule)
    for ent_schedules in entities.values():
        for sub_schedule in ent_schedules.values():
            for var_name in sub_schedule.keys():
                sub_schedule[var_name] = sub_schedule[var_name].tolist()

    if isinstance(file_name, str):
        if not file_name.endswith(".json"):
            file_name = file_name + ".json"
        with open(file_name, 'w') as outfile:
            json.dump(entities, outfile)
    else:
        json.dump(entities, file_name)


def schedule_to_csv(input_list, file_name, delimiter=";", schedule=None):
    """
    Write the optimized schedule of all entities to a CSV file.

    Parameters
    ----------
    input_list : list
        List of entities.
    file_name : str or file-like object
        Specify the file name or an open file where the csv should be saved
        in. If file_name is a string and it does not have the `.csv`
        extension it will be appended.
    delimiter : str
        CSV file delimiter character.
    schedule : str or list, optional
           Schedule or list of schedules to save.

           - `None` : Current schedule of entity
           - 'default' : Normal schedule
           - 'ref' : Reference schedule
    """
    sub_schedules = []
    headers = []

    max_schedule_length = 0
    entities = schedule_to_dict(input_list, schedule)
    for ent, ent_schedules in entities.items():
        for ent_schedule_name, sub_schedule in ent_schedules.items():
            for var_name, var_schedule in sub_schedule.items():
                headers.append("_".join([ent, ent_schedule_name, var_name]))
                sub_schedules.append(var_schedule+0.0)
                max_schedule_length = max(max_schedule_length, len(var_schedule))

    if isinstance(file_name, str) and not file_name.endswith(".csv"):
        file_name = file_name + ".csv"
    with open(str(file_name), 'w', newline='') as file:
        writer = csv.writer(file, delimiter=delimiter, escapechar='', quoting=csv.QUOTE_NONE)
        writer.writerow(headers)

        row = 0
        while row < max_schedule_length:
            row_string = []
            for schedule in sub_schedules:
                if row < len(schedule):
                    row_string.append(str(schedule[row]))
                else:
                    row_string.append('')
            writer.writerow(row_string)
            row += 1
    return
