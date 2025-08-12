# look up station uri in dataset meta info and harvest contributor info for that station into a dataframe
def getStationRolesFromFilePid(fpid, debug=False):
    import json, requests
    import pandas as pd
    from requests.structures import CaseInsensitiveDict
    from icoscp.dobj import Dobj

    if 'https://meta.icos-cp.eu/resources/stations/' in fpid:
        stationurl = fpid
    elif len(fpid) < 7:
        stationurl = 'https://meta.icos-cp.eu/resources/stations/' + fpid
    else:
        obj = Dobj(fpid)
        meta = obj.meta
        # citation=meta['references']['citationString']
        stationurl = \
        meta['specificInfo']['acquisition']['station']['org']['self']['uri']

    if debug: print(stationurl)
    df = pd.DataFrame()

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    resp = requests.get(stationurl, headers=headers)
    info = json.loads(resp.text)

    if 'ATMO_' in stationurl:
        # if debug: print(info)
        authors = meta['references']['authors']
        # if debug: print(authors)
        for author in authors:
            fname = author['firstName']
            lname = author['lastName']
            uri = author['self']['uri']
            orcid = ''
            wght = 30
            start = None
            end = None
            df = df.append(
                {'fname': fname, 'lname': lname, 'orcid': orcid, 'uri': uri,
                 'weight': wght, 'start': start, 'end': end},
                ignore_index=True)
    else:
        for person in info['staff']:
            fname = person['person']['firstName']
            lname = person['person']['lastName']
            # if debug: print(person)
            uri = person['person']['self']['uri']
            try:
                orcid = person['person']['orcid']
            except:
                orcid = ''
            try:
                wght = person['role']['weight']
            except:
                wght = None
            try:
                start = person['role']['start']
            except:
                start = None
            try:
                end = person['role']['end']
            except:
                end = None
            df = df.append(
                {'fname': fname, 'lname': lname, 'orcid': orcid, 'uri': uri,
                 'weight': wght, 'start': start, 'end': end},
                ignore_index=True)

    if 'HFD' in stationurl:
        df = df.append({'fname': 'Chris',
                        'lname': 'Rennick',
                        'orcid': '0000-0003-4993-0156',
                        'uri': 'http://meta.icos-cp.eu/resources/people/chris_rennick',
                        'weight': 100,
                        'start': None,
                        'end': None},
                       ignore_index=True)
    if 'ZOT' in stationurl:
        df = df.append({'fname': 'Sönke',
                        'lname': 'Zähle',
                        'orcid': '0000-0001-5602-7956',
                        'uri': 'http://meta.icos-cp.eu/resources/people/S%C3%B6nke_Zaehle',
                        'weight': 100,
                        'start': None,
                        'end': None},
                       ignore_index=True)

    if debug:
        pass
        # print(df)

    return df, info
#df,info=getStationRolesFromFilePid('https://meta.icos-cp.eu/resources/stations/AS_MHD',debug=True)
#df,info=getStationRolesFromFilePid('https://meta.icos-cp.eu/resources/stations/ATMO_GIC',debug=True)
#df,info=getStationRolesFromFilePid('v6pScuq5S85_PzM4ZWsk4G9y',debug=True)
#df


def ncwrite2txt(ncfile):
    import os
    import xarray as xr

    data = xr.open_dataset(ncfile)
    df = data.to_dataframe()
    pre, ext = os.path.splitext(ncfile)
    txtfile = pre + '.csv'
    df = df.to_csv(txtfile)

    return df


def newfileinfo(uri:str):
    import requests
    response = requests.get(uri,headers={"Accept": "application/json"})
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        # Print an error message
        print('Error fetching data')
        return('Error')


#------------------------------------------------------------------------------------------------------------
# Unused functions from utils.py
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
