# Standard library imports.
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Optional, Any
import json
import sys

# Related third party imports.
from icoscp_core import icos, auth
from icoscp_core.sparql import SparqlResults
from requests.utils import cookiejar_from_dict
import datetime as dt
import requests

# Local application/library specific imports.
from icoscp_obspack.constants import icons as i


def is_notebook():
    """Detect if running in a Jupyter notebook."""
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
        return shell == 'ZMQInteractiveShell'
    except Exception:
        return False


def progress_bar(current: int = None, total: int = None, bar_length: int = 20) -> None:
    """Outputs a loading-like bar."""
    fraction = current / total
    arrow = int(fraction * bar_length - 1) * '-' + '>'
    padding = int(bar_length - len(arrow)) * ' '
    percent = int(fraction * 100)
    bar = f'Getting file metadata [{arrow}{padding}] {percent}%'

    if is_notebook():
        print(bar, end='\r', flush=True)
        if current == total:
            print()
    else:
        # Terminal or IDE console
        sys.stdout.write('\r' + bar)
        sys.stdout.flush()
        if current == total:
            sys.stdout.write(f' {i.ICON_CHECK}\n')


def new_file_info(uri: str = None):
    response = requests.get(uri, headers={'Accept': 'application/json'})
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print('Error fetching data')
        return 'Error'


def t2dt(atime: float) -> dt.datetime:
    """Converts a fractional year timestamp to a datetime object."""
    year = int(atime)
    remainder = atime - year
    boy = dt.datetime(year, 1, 1)
    eoy = dt.datetime(year + 1, 1, 1)
    seconds = remainder * (eoy - boy).total_seconds()
    return boy + dt.timedelta(seconds=seconds)


def write_json(path: str, content: dict[str, Any], convert_posix: bool = True
               ) -> None:
    """Write dictionary to json file."""
    if convert_posix:
        posix_to_str(content)
    with open(file=path, mode='w+') as json_handle:
        json.dump(content, json_handle, indent=4)
    return


def read_json(path: str) -> Any:
    """Read dictionary from json file."""
    with open(file=path, mode='r') as json_handle:

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
        for key, sub_dict in content.items():
            if 'file_path' in sub_dict:
                sub_dict['file_path'] = str(sub_dict['file_path'])
            if 'json_file_path' in sub_dict:
                sub_dict['json_file_path'] = str(sub_dict['json_file_path'])
    return


# Todo: refactor this to correctly handle posix paths in dictionaries
#  and dictionaries within dictionaries.
def str_to_posix(content: dict[str, Any]) -> None:
    """Convert string file paths to PosixPaths."""
    if 'file_path' in content:
        content['file_path'] = Path(content['file_path'])
    else:
        for key, sub_dict in content.items():
            if 'file_path' in sub_dict:
                sub_dict['file_path'] = Path(sub_dict['file_path'])
            if 'json_file_path' in sub_dict:
                sub_dict['json_file_path'] = Path(sub_dict['json_file_path'])
    return


def get_cookie_jar() -> Optional[CookieJar]:
    cookie_string = str()
    cookie_jar: Optional[CookieJar] = None
    cookie_dict = dict()
    try:
        cookie_string = icos.auth.get_token().cookie_value
    except Exception as e:
        if "Config file does not exist" in str(e):
            icos.auth.init_config_file()
            cookie_string = icos.auth.get_token().cookie_value
        elif "Incorrect user name or password" in str(e):
            icos.auth.init_config_file()
            cookie_string = icos.auth.get_token().cookie_value
        else:
            print("Got a weird exception...", e)
    else:
        # Convert string to dictionary.
        cookie_dict = {cookie.split("=")[0]: cookie.split("=")[1] for
                       cookie in cookie_string.split("; ")}
    finally:
        if cookie_string:
            # Convert dictionary to RequestsCookieJar.
            cookie_jar = cookiejar_from_dict(cookie_dict)
    return cookie_jar


def get_prev_by_name(anchor: str) -> str:
    prev_version = str()

    query_template = """
    PREFIX cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
    
    SELECT ?dobj
    WHERE {
        VALUES ?spec {
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackTimeSerieResult>
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackCH4TimeSeriesResult>
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackN2oTimeSeriesResult>
        }
        ?dobj cpmeta:hasObjectSpec ?spec .
        ?dobj cpmeta:hasName ?fileName .
        FILTER(STRSTARTS(str(?fileName), "#anchor"))
        FILTER NOT EXISTS {[] cpmeta:isNextVersionOf ?dobj}
        FILTER EXISTS {?dobj cpmeta:hasSizeInBytes []}
    }
    """
    query = query_template.replace('#anchor', anchor)
    sparql_res: SparqlResults = icos.meta.sparql_select(query=query)
    if sparql_res.bindings:
        prev_uri = sparql_res.bindings[0]['dobj'].uri
        prev_version = prev_uri.split('/')[-1]
    # assert prev_version != ''
    return prev_version


def get_hash_sum(file_path: str | Path = None) -> str:
    """Calculate and return hash-sum of given file."""
    with open(file=file_path, mode='rb') as f_hdl:
        data = f_hdl.read()
    return hashlib.sha256(data).hexdigest()
