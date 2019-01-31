import numpy as np


def compute_blocks(timer, time):
    """Compute load blocks.

    Search time for blocks of `1`. Return first and last indexes of each
    block as tuples. For the last block calculate the portion of the whole
    block which existed if the horizon was larger.

    Parameters
    ----------
    timer : Timer
    time : array_like of {0, 1}
        Array of all possible times.

    Returns
    -------
    list of tuple :
        Blocks of loading time.
    float :
        Portion of the last contained block to the whole block.
    """
    ts_in_day = timer.time_in_day()
    time_dis = timer.timeDiscretization
    horizon = timer.timestepsUsedHorizon
    num = int(horizon / (86400 / time_dis)) + 2
    if num < 3:
        num = 3
    time = np.tile(time, num)
    blocks = []
    current_n = 0
    last_val = 0
    n = 0
    val = 0
    for n, val in enumerate(time[ts_in_day:ts_in_day+horizon]):
        if last_val == 0 and val == 1:
            current_n = n
        elif last_val == 1 and val == 0:
            blocks.append((current_n, n))
        last_val = val
    portion = 1
    additional_times = 0
    if val == 1:
        blocks.append((current_n, n+1))
        for val in time[ts_in_day+horizon:]:
            if val == 1:
                additional_times += 1
            else:
                break
        last_block_len = blocks[-1][1] - blocks[-1][0]
        portion = last_block_len / (last_block_len + additional_times)
    return blocks, portion


def compute_inverted_blocks(timer, time):
    """Compute load blocks.

    Search time for blocks of `0`. Return first and last indexes of each
    block as tuples. For the last block calculate the portion of the whole
    block which existed if the horizon was larger.

    Parameters
    ----------
    timer : Timer
    time : array_like of {0, 1}
        Array of all possible times.

    Returns
    -------
    list of tuple :
        Blocks of loading time.
    float :
        Portion of the last contained block to the whole block.
    """
    ts_in_day = timer.time_in_day()
    time_dis = timer.timeDiscretization
    horizon = timer.timestepsUsedHorizon
    num = int(horizon / (86400 / time_dis)) + 2
    if num < 3:
        num = 3
    time = np.tile(time, num)
    blocks = []
    current_n = 1
    last_val = 1
    n = 0
    val = 0
    for n, val in enumerate(time[ts_in_day:ts_in_day+horizon]):
        if last_val == 1 and val == 0:
            current_n = n
        elif last_val == 0 and val == 1:
            blocks.append((current_n, n))
        last_val = val
    portion = 1
    additional_times = 0
    if val == 0:
        blocks.append((current_n, n+1))
        for val in time[ts_in_day+horizon:]:
            if val == 0:
                additional_times += 1
            else:
                break
        last_block_len = blocks[-1][1] - blocks[-1][0]
        portion = last_block_len / (last_block_len + additional_times)
    return blocks, portion
