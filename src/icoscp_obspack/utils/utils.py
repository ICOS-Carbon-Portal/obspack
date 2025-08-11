# Standard library imports.
from datetime import datetime

# Local application/library specific imports.
from icoscp_obspack.constants import icons as i

def timeit(previous_time: datetime, message: str, print_msg: bool) -> datetime:
    """
    Print the time elapsed since the previous time and the current time.
    :param `previous_time`:
        A datetime object representing the previous time.
    :param `message`:
        A message to print along with the elapsed time.
    """
    current_time = datetime.now()
    elapsed_time = current_time - previous_time
    message_elapsed_time = f"{elapsed_time.total_seconds():6.2f} seconds"
    if print_msg:
        print(f'      {message:<100}{message_elapsed_time:>16}')
    return current_time


#------------------------------------------------------------------------------------------------------------
# Unused functions
#------------------------------------------------------------------------------------------------------------
# These functions are not currently used in the codebase, but they may be useful in the future.
# They are kept here for reference and potential future use.

import json
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any

def progress_bar(current: int, total: int, bar_length: int = 20) -> None:
    """Outputs a loading-like bar."""
    fraction = current / total
    arrow = int(fraction * bar_length - 1) * '-' + '>'
    padding = int(bar_length - len(arrow)) * ' '
    percent = int(fraction * 100)
    bar = f'Getting file metadata [{arrow}{padding}] {percent}%'

    # Terminal or IDE console
    sys.stdout.write('\r' + bar)
    sys.stdout.flush()
    if current == total:
        sys.stdout.write(f' {i.ICON_CHECK}\n')


def sinceEpoch(date: date | datetime) -> float:
    """Returns seconds since epoch"""
    return time.mktime(date.timetuple())


def toYearFraction(date: date) -> float:
    year = date.year
    startOfThisYear = datetime(year=year, month=1, day=1)
    startOfNextYear = datetime(year=year+1, month=1, day=1)
    yearElapsed = sinceEpoch(date) - sinceEpoch(startOfThisYear)
    yearDuration = sinceEpoch(startOfNextYear) - sinceEpoch(startOfThisYear)
    fraction = yearElapsed/yearDuration
    return date.year + fraction


def write_json(path: str, content: dict[str, Any], convert_posix: bool = True) -> None:
    """Write dictionary to json file."""
    if convert_posix:
        posix_to_str(content)
    with open(file=path, mode='w+') as json_handle:
        json.dump(content, json_handle, indent=4)


def read_json(path: str) -> Any:
    """Read dictionary from json file."""
    with open(file=path) as json_handle:
        json_data = json.load(json_handle)
    str_to_posix(json_data)
    return json_data


# Todo: refactor this to correctly handle posix paths in dictionaries
#  and dictionaries within dictionaries.
def posix_to_str(content: dict[str, Any]) -> None:
    """Convert PosixPaths to string file paths."""
    if 'file_path' in content:
        content['file_path'] = str(content['file_path'])
    else:
        for _key, sub_dict in content.items():
            if 'file_path' in sub_dict:
                sub_dict['file_path'] = str(sub_dict['file_path'])
            if 'json_file_path' in sub_dict:
                sub_dict['json_file_path'] = str(sub_dict['json_file_path'])


# Todo: refactor this to correctly handle posix paths in dictionaries
#  and dictionaries within dictionaries.
def str_to_posix(content: dict[str, Any]) -> None:
    """Convert string file paths to PosixPaths."""
    if 'file_path' in content:
        content['file_path'] = Path(content['file_path'])
    else:
        for _key, sub_dict in content.items():
            if 'file_path' in sub_dict:
                sub_dict['file_path'] = Path(sub_dict['file_path'])
            if 'json_file_path' in sub_dict:
                sub_dict['json_file_path'] = Path(sub_dict['json_file_path'])
