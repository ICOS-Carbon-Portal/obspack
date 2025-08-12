# Standard library imports.
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Related third party imports.
import pandas as pd

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

def get_hash_sum(path: Path) -> str:
    """Calculate and return hash-sum of given file."""
    if not path.exists():
        raise ValueError('A valid file path must be provided.')
    with open(file=path, mode='rb') as f_hdl:
        data = f_hdl.read()
    return hashlib.sha256(data).hexdigest()

def year_fraction(date_and_time: pd.Timestamp):
    start = datetime(date_and_time.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(date_and_time.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    year_fraction = (date_and_time - start) / (end - start)
    return date_and_time.year + year_fraction

def extract_temporal_components(date_and_time: pd.Timestamp, offset_in_sec: int | float = 0):
    date_and_time_with_offset = date_and_time + timedelta(seconds=offset_in_sec)
    return [
        date_and_time_with_offset.year, date_and_time_with_offset.month, date_and_time_with_offset.day,
        date_and_time_with_offset.hour, date_and_time_with_offset.minute, 0]

def t2dt(timepoint: float) -> datetime:
    """Convert a fractional year timestamp to a datetime object."""
    year = int(timepoint)
    remainder = timepoint - year
    boy = datetime(year, 1, 1)
    eoy = datetime(year + 1, 1, 1)
    seconds = remainder * (eoy - boy).total_seconds()
    return boy + timedelta(seconds=seconds)
