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
import os
import os.path as op
import matplotlib.pyplot as plt

from pycity_scheduling.classes import Battery, ElectricalVehicle, CombinedHeatPower


_known_varnames = {
    "p_el": plt.get_cmap("tab20").colors[:2],
    "e_el": plt.get_cmap("tab20").colors[8:10],
    "p_th": plt.get_cmap("tab20").colors[2:4],
    "e_th": plt.get_cmap("tab20").colors[6:8]
}

_other_colors = [plt.get_cmap("tab20").colors[i:2+i] for i in range(10, 20, 2)]


def _extended_schedule(var_name, schedule):
    if var_name.startswith("e_"):
        ini = None
        schedule = np.concatenate([[ini], schedule])
        drawstyle = "default"
    else:
        schedule = np.concatenate([schedule, schedule[-1:]])
        drawstyle = "steps-post"
    return schedule, drawstyle


def plot_entity(entity, schedule=None, ax=None, title=None):
    """
    Plot a single entity into axis.

    Parameters
    ----------
    entity : OptimizationEntity
        Entity that should be plotted.
    schedule : str or list, optional
       Schedule or list of schedules to save. Defaults to the current schedule.
       At most two schedules can be plotted.

       - `None` : Current schedule of entity
       - 'default' : Normal schedule
       - 'ref' : Reference schedule
    ax : matplotlib.Axes, optional
        Axes the Entity should be plotted into. Shows the plot in a new figure if not specified.
    title : str, optional
        Title of the plot. Uses the name of the entity if not specified.
    """
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = None

    if schedule is None:
        schedule_names = [entity.current_schedule]
    elif isinstance(schedule, str):
        schedule_names = [schedule]
    elif isinstance(schedule, list):
        if len(schedule) > 2:
            raise ValueError("Amount of schedules to plot is too large.")
        schedule_names = schedule
    else:
        raise ValueError("Unknown type for schedule.")

    var_colors = _known_varnames.copy()
    unknown_vars = entity.schedule.keys() - _known_varnames.keys()
    if isinstance(entity, Battery):
        unknown_vars.discard("p_el_demand")
        unknown_vars.discard("p_el_supply")
        unknown_vars.discard("p_state")
    if isinstance(entity, ElectricalVehicle):
        unknown_vars.discard("p_el_drive")
        unknown_vars.discard("p_state")
    if isinstance(entity, CombinedHeatPower):
        unknown_vars.discard("total_device")
        unknown_vars.discard("current_device")
    for i, uv in enumerate(unknown_vars):
        if i >= len(_other_colors):
            raise ValueError("Too many variables for entity to plot.")
        var_colors[uv] = _other_colors[i]
    linestyles = ['-', ':']
    min_y = np.infty
    max_y = -np.infty
    for i, entity_schedule in enumerate(schedule_names):
        for var_name, var_schedule in entity.schedules[entity_schedule].items():
            if var_name not in var_colors:
                continue
            c = var_colors[var_name][i]
            xs = [x * entity.time_slot for x in range(entity.simu_horizon+1)]
            extended_schedule, drawstyle = _extended_schedule(var_name, var_schedule)
            if schedule is None:
                label = var_name
            else:
                label = entity_schedule + "_" + var_name
            ax.plot(xs, extended_schedule, color=c, label=label, drawstyle=drawstyle, linewidth=2,
                    linestyle=linestyles[i])
            min_y = min(min_y, min(var_schedule))
            max_y = max(max_y, max(var_schedule))

    if min_y < 0.0:
        min_y = min_y*1.5
    elif min_y > 0.0:
        min_y = min_y * 0.5
    else:
        min_y = -0.1*max_y

    if max_y < 0.0:
        max_y = max_y*0.5
    elif max_y > 0.0:
        max_y = max_y * 1.5
    else:
        max_y = -0.1*min_y

    if title is None:
        ax.set_title(str(entity))
    else:
        ax.set_title(title)
    ax.set_ylim([min_y, max_y])
    ax.set_xlabel("Time in h")
    ax.legend(loc='upper right')
    if fig is not None:
        plt.show()
    return


def plot_imbalance(entity, schedule=None, var_name="p_el", ax=None, title=None):
    """
    Plot the imbalance of a schedule to its sub-entities.

    For entity containers and other similar entities with sub-entities the
    schedule of some variables should be the equal to the sum of the schedule
    of these variables of the sub-entities. This function plots this imbalance.

    Parameters
    ----------
    entity : OptimizationEntity
        Entity that should be plotted.
    schedule : str or list, optional
       Schedule or list of schedules to save. Defaults to the current schedule.
       At most two schedules can be plotted.

       - `None` : Current schedule of entity
       - 'default' : Normal schedule
       - 'ref' : Reference schedule
    var_name : str, optional
        The name of the variable to plot the imbalance for. Defaults to "p_el".
    ax : matplotlib.Axes, optional
        Axes the Entity should be plotted into. Shows the plot in a new figure if not specified.
    title : str, optional
        Title of the plot. Uses the name of the entity if not specified.
    """
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = None

    if schedule is None:
        schedule_names = [entity.current_schedule]
    elif isinstance(schedule, str):
        schedule_names = [schedule]
    elif isinstance(schedule, list):
        schedule_names = schedule
    else:
        raise ValueError("Unknown type for schedule.")

    min_y = np.infty
    max_y = -np.infty
    for entity_schedule in schedule_names:
        imbalance = entity.schedules[entity_schedule][var_name].copy()
        for lower_entity in entity.get_lower_entities():
            imbalance -= lower_entity.schedules[entity_schedule][var_name]
        xs = [x * entity.time_slot for x in range(entity.simu_horizon + 1)]
        extended_schedule, drawstyle = _extended_schedule(var_name, imbalance)
        ax.plot(xs, extended_schedule, drawstyle=drawstyle, linewidth=1.5, label=entity_schedule)
        min_y = min(min_y, min(imbalance))
        max_y = max(max_y, max(imbalance))

    if min_y < 0.0:
        min_y = min_y*1.5
    elif min_y > 0.0:
        min_y = min_y * 0.5
    else:
        min_y = -0.1*max_y

    if max_y < 0.0:
        max_y = max_y*0.5
    elif max_y > 0.0:
        max_y = max_y * 1.5
    else:
        max_y = -0.1*min_y

    ax.set_ylim([min_y, max_y])
    if title is None:
        ax.set_title("Imbalance of entity {} for {}".format(str(entity), var_name))
    else:
        ax.set_title(title)
    ax.set_xlabel("Time in h")
    ax.legend(loc='upper right')
    if fig is not None:
        plt.show()
    return


def plot_entity_directory(entity, schedule=None, directory_path=None, levels=None, extension="png"):
    """
    Plot the entity and its sub-entities into a directory.

    Creates the directories and places the plots in them.
    Parameters
    ----------
    entity : OptimizationEntity
        Entity that should be plotted.
    schedule : str or list, optional
       Schedule or list of schedules to save. Defaults to the current schedule.
       At most two schedules can be plotted.
       `None` : Current schedule of entity
       'default' : Normal schedule
       'ref' : Reference schedule
    directory_path : str, optional
        Directory path in which plots are stored. Defaults to the name of the
        entity in the current directory.
    levels : int, optional
        The level of sub-entities to plot. Defaults to all sub-entities.

        - `0` : Only print city district.
        - `1` : Only print city district and buildings.
        - `2` : Print city district, buildings and their lower entities.
        - `...` : ...
    extension : str, optional
        File extension (i.e., the file format) of the figures to be stored in the given directory.
    """

    entities = [entity]
    directories = [""]
    if directory_path is None:
        directory_path = op.join(os.getcwd(), str(entity))
    os.makedirs(directory_path, exist_ok=True)
    while len(entities) != 0:
        next_entities = []
        next_directories = []
        for entity, directory in zip(entities, directories):
            if levels is None or levels > 0:
                lower_entities = list(entity.get_lower_entities())
            else:
                lower_entities = []
            if len(lower_entities) > 0 and directory != "":
                path = op.join(directory_path, directory, str(entity))
                os.makedirs(path, exist_ok=True)
            else:
                # first level entity or no lower entities
                path = op.join(directory_path, directory)

            fig, ax = plt.subplots()
            plot_entity(entity, schedule=schedule, ax=ax)
            fig.savefig(op.join(path, str(entity) + "." + extension))

            next_entities.extend(lower_entities)
            next_directories.extend([path] * len(lower_entities))

        if levels is not None:
            levels -= 1
        entities = next_entities
        directories = next_directories
    return
