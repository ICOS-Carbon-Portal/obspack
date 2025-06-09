# Standard library imports.
import datetime as dt
import json
import pickle
import zipfile
from pathlib import Path
from typing import IO

# Related third party imports.
import pandas as pd
import requests
from icoscp.dobj import Dobj
from icoscp_core.icos import meta, ATMO_STATION
from requests.structures import CaseInsensitiveDict

# Local application/library specific imports.
from icoscp_core.metacore import AtcStationSpecifics, DataObject, SpatioTemporalMeta, StationTimeSeriesMeta, VarMeta
from icoscp_obspack.config import Config
from icoscp_obspack.constants import envri
from icoscp_obspack.netcdf import write_nc
from icoscp_obspack.utils.citation import cleanup_author_list, citation
from icoscp_obspack.utils.plotting import plot_timeseries_station
from icoscp_obspack.utils.sparql_queries import dobjs_from_station_and_spec_list
from icoscp_obspack.utils.utils import progress_bar, t2dt, toYearFraction, doi_citation


specs_per_gas = {
    "co2": ['atcCo2Product', 'atcCo2L2DataObject', 'atcGHGFastTrackNRTDataObject', 'atcCo2NrtGrowingDataObject'],
    "ch4": ['atcCh4Product', 'atcCh4L2DataObject', 'atcGHGFastTrackNRTDataObject', 'atcCh4NrtGrowingDataObject'],
    "n2o": ['atcN2oProduct', 'atcN2oL2DataObject', 'atcGHGFastTrackNRTDataObject', 'atcN2oNrtGrowingDataObject'],
    "co": ['atcCoProduct', 'atcCoL2DataObject', 'atcGHGFastTrackNRTDataObject', 'atcCoNrtGrowingDataObject']
}

# initialisation routine to set up global structures and initialise data
def init():
    global colnames
    global nrcols
    global skip
    global obspack_set
    atc_drought_header = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                          'Hour', 'Minute', 'DecimalDate', 'co2', 'Stdev',
                          'NbPoints', 'Flag', 'InstrumentId', 'QualityId',
                          'InternalFlag', 'AutoDescriptiveFlag',
                          'ManualDescriptiveFlag', 'DataOrigin']
    atc_atmprod_header = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                          'Hour', 'Minute', 'DecimalDate', 'co2', 'Stdev',
                          'NbPoints', 'Flag', 'InstrumentId', 'QualityId',
                          'LTR', 'CMR', 'STTB', 'QcBias', 'QcBiasUncertainty',
                          'Origin', 'OriginalFlag']
    atc_l2_header = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day', 'Hour',
                     'Minute', 'DecimalDate', 'co2', 'Stdev', 'NbPoints',
                     'Flag', 'InstrumentId', 'QualityId', 'LTR', 'CMR', 'STTB',
                     'QcBias', 'QcBiasUncertainty']
    atc_nrt_header = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day', 'Hour',
                      'Minute', 'DecimalDate', 'co2', 'Stdev', 'NbPoints',
                      'Flag', 'InstrumentId', 'QualityId', 'InternalFlag',
                      'AutoDescriptiveFlag', 'ManualDescriptiveFlag']
    atc_l2_header_ch4 = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                         'Hour', 'Minute', 'DecimalDate', 'ch4', 'Stdev',
                         'NbPoints', 'Flag', 'InstrumentId', 'QualityId',
                         'LTR', 'CMR', 'STTB', 'QcBias', 'QcBiasUncertainty']
    atc_l2_header_co = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                        'Hour', 'Minute', 'DecimalDate', 'co', 'Stdev',
                        'NbPoints', 'Flag', 'InstrumentId', 'QualityId', 'LTR',
                        'CMR', 'STTB', 'QcBias', 'QcBiasUncertainty']
    atc_l2_header_n2o = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                         'Hour', 'Minute', 'DecimalDate', 'n2o', 'Stdev',
                         'NbPoints', 'Flag', 'InstrumentId', 'QualityId',
                         'LTR', 'CMR', 'STTB', 'QcBias', 'QcBiasUncertainty']
    atc_fast_header = ['Site', 'SamplingHeight', 'Year', 'Month', 'Day',
                       'Hour', 'Minute', 'DecimalDate', 'co2', 'Stdev',
                       'NbPoints', 'Flag', 'InstrumentId', 'QualityId', 'LTR',
                       'CMR', 'STTB', 'QcBias', 'QcBiasUncertainty']

    colnames = [atc_atmprod_header, atc_nrt_header, atc_fast_header, atc_l2_header]

    nrcols = [22, 18, 20, 20]
    skip = [45, 39, 45, 45]
    obspack_set = {'doi_collection': 'https://doi.org/10.18160/' + c.doi,
                   'icos_class': [1, 2],
                   'non-icos': True,
                   'version': '11.1',
                   'contributors': [],
                   'contrib_ORCID': [],
                   'other': 'NA',
                   }


def process_obspack() -> None:
    # First scan to determine all stations and files, collect
    # attribution metadata.
    # First run to collect citation data on contributors
    run_all(process=False)
    c.col_contribs = cleanup_author_list(contribs=c.col_contribs)

    # Save contributor and author info as json for the DOI minting.
    auth = Path(c.output, f'authors_{c.gas}.json')
    contribs = Path(c.output, f'contributors_{c.gas}.json')
    with open(auth, 'w') as file_handle:
        file_handle.write(citation(c, as_contrib=False))
    with open(contribs, 'w') as file_handle:
        file_handle.write(citation(c, as_contrib=True))


def get_meta_dobjs(dobjs: list[str]) -> list[DataObject]:
    metadata_dobjs = []
    for pos, dobj_uri in enumerate(dobjs):
        progress_bar(current=pos+1, total=len(dobjs))
        dobj_meta = meta.get_dobj_meta(dobj_uri)
        if (
            isinstance(dobj_meta.specificInfo, StationTimeSeriesMeta)
            and isinstance(dobj_meta.specificInfo.columns, VarMeta)
            and c.gas in [col.label for col in dobj_meta.specificInfo.columns]
        ):
            metadata_dobjs.append(dobj_meta)
    return metadata_dobjs


def get_list_of_dobjs_from_station_and_list_of_specs(specs: list, station_id: str) -> list[str]:
    """Query atmospheric data.

    Create and execute a sparql query to retrieve atmospheric data that
    we need to explore.
    """
    sparql_query = dobjs_from_station_and_spec_list(
        [envri.ICOS_CONFIG.meta_resources_prefix + spec for spec in specs],
        station_id,
        c.submitted_after)
    response = requests.get(
        envri.ICOS_CONFIG.sparql, params={'format': 'json', 'query': sparql_query})
    dobjs_json = response.json()
    dobjs = [binding.get("dobj", {}).get('value') for binding in dobjs_json['results']['bindings']]
    return dobjs


def run_all(process=False):

    def_citations = [doi_citation('10.18160/0F1E-DKXT'),
                     doi_citation('10.18160/ATM_NRT_CO2_CH4')]

    # Unique dataset nr in the obspack product.
    if c.gas == 'co2':
        nr = 1000
    elif c.gas == 'ch4':
        nr = 2000
    elif c.gas == 'n2o':
        nr = 3000
    elif c.gas == 'co':
        nr = 4000

    previous_station = ''

    for station in meta.list_stations(ATMO_STATION):
        # Only atmospheric stations
        station_meta = meta.get_station_meta(station.uri)

        if station.id == previous_station:
            print(f'Skipping station {station.id} because it was already processed.')
            previous_station = station.id
            continue
        previous_station = station.id

        if not isinstance(station_meta.specificInfo, AtcStationSpecifics):
            print(f'Skipping station {station.id} because it is not an ATC station.')
            continue

        if station_meta.specificInfo.stationClass not in ['1', '2']:
            print(f'Skipping station {station.id} because it is not a level 1 or 2 station.')
            continue

        dobjs = get_list_of_dobjs_from_station_and_list_of_specs(specs_per_gas[c.gas], station.id)
        metadata_dobjs = get_meta_dobjs(dobjs)

        # Look up the list of relevant data objects for these stations
        # and make a list of associated sampling heights.
        available_heights = set()
        for dobj in metadata_dobjs:
            if (isinstance(dobj.specificInfo, StationTimeSeriesMeta)
                and dobj.specificInfo.acquisition.samplingHeight is not None):
                if (station.id == 'HUN') and ((dobj.specificInfo.acquisition.samplingHeight - 48.0) < 1):
                    available_heights.add(50)
                else:
                    available_heights.add(dobj.specificInfo.acquisition.samplingHeight)
            else:
                available_heights.add(0.0)

        # Go through the sampling heights of each station one by one.
        for height in sorted(available_heights):
            treat_data = []
            citations = []
            c.d_files = []
            for dobj in metadata_dobjs:
                if do.hgh is not None:
                    if abs(float(do.hgh) - height) < 2.5:
                        if (station.id == 'JFJ') and (
                                abs(float(do.hgh) - 5.0) < 1):
                        else:
                            s = Dobj(do.uri)
                            treat_data.append(do.uri)
                            if station.id == 'HFD':
                                add_roles(pid='HFD')
                            else:
                                add_roles(pid=do.uri)
                            citations = citations + [s.citation]
                            c.d_files = c.d_files + [do.uri.replace(
                                'https://meta.icos-cp.eu/objects/',
                                '')]
            if len(treat_data) > 1:
                citations = def_citations + citations
            # Station class 1 or 2; ICOS stations only.
            if len(treat_data) > 0:
                print(station.id, ' Height:', height, ' Class:', station_meta.specificInfo.stationClass,
                        ' NrFiles:', len(treat_data))
                if process:
                    lab_nr = c.icos_stations[c.icos_stations.Hist == station.id].NOAALabNr.values[0]
                    if len(hgh) > 1:
                        file_name = (
                                c.gas + '_' + station.id.lower() +
                                '_tower-insitu_' + str(int(lab_nr)) +
                                '_allvalid-' + str(int(h)) + 'magl')
                    else:
                        file_name = (
                                c.gas + '_' + station.id.lower() +
                                '_surface-insitu_' + str(int(lab_nr)) +
                                '_allvalid')
                    height = int(h)
                    df = get_icos_ts(dobj_list=treat_data, hgh=height, download=True)
                    if df.empty:
                        print('No data found for station ' + station.id + ' ' + str(height))
                        continue

                    if c.do_png:
                        df = plot_timeseries_station(
                            c=c, icos_df=df, st_id=station.id, hgh=height, f_name=file_name)

                    c.file_contribs = cleanup_author_list(c.file_contribs)
                    #person = person_list()
                    list_of_names = [f'{f} {l}' for f, l in zip(c.file_contribs['fname'],
                                                                c.file_contribs['lname'])]
                    persons = ' AND '.join(list_of_names)
                    try:
                        write_nc(
                            c, file_name, df, station_meta, citations,
                            obspack_set, persons=persons, hgh=h,
                            calib_scale=calib, factor=fact,
                            nc_cnt=nr, doi_cite=c.doi
                        )
                        #write_nc(
                        #    c, file_name, df, station_meta, citations,
                        #    obspack_set, persons=person, hgh=h, lab_id=466,
                        #    nc_cnt=nr, doi_cite=doi
                        #)
                    except Exception:
                        print('Error writing: ', file_name)
                        raise

                    row = pd.DataFrame([{
                        'fname': file_name,
                        'folder': c.nc,
                        'station': station.id,
                        'hgh': h,
                        'hash': '',
                        'Handle': ''
                    }])
                    c.produced = pd.concat([c.produced, row], ignore_index=True)
                    c.produced.to_csv(Path(c.output, 'produced.csv'))
                    nr = nr + 1


def add_roles(pid: str):
    # Add contributors for file with this PID to the global contribs dataframes
    roles, info = get_roles(f_pid=pid)
    c.col_contribs = pd.concat([roles, c.col_contribs])
    return roles


# look up station uri in dataset meta info and harvest contributor info for that station into a dataframe
def get_roles(f_pid: str):
    if envri.ICOS_CONFIG.station_prefix in f_pid:
        station_url = f_pid
    elif len(f_pid) < 7:
        station_url = envri.ICOS_CONFIG.station_prefix + f_pid
    else:
        obj = Dobj(f_pid)
        meta = obj.meta
        # citation=meta['references']['citationString']
        station_url = \
            meta['specificInfo']['acquisition']['station']['org']['self']['uri']
    hash_sum = (str(f_pid)).split('/')[-1]
    df_pkl_path = Path(c.pickle, f'{hash_sum}.pkl')
    json_pkl_path = Path(c.pickle, f'{hash_sum}_info.pkl')
    if c.debug and not c.refresh_pickles:
        with open(df_pkl_path, 'rb') as f:
            pkl_df = pickle.load(f)
        with open(json_pkl_path, 'rb') as f:
            pkl_info = pickle.load(f)
        return pkl_df, pkl_info
    else:
        df = pd.DataFrame()
        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"
        resp = requests.get(station_url, headers=headers)
        info = json.loads(resp.text)
        if 'ATMO_' in station_url:
            # if debug: print(info)
            authors = meta['references']['authors']
            # if debug: print(authors)
            for author in authors:
                row = pd.DataFrame([{
                    'fname': author['firstName'],
                    'lname': author['lastName'],
                    'orcid': '',
                    'uri': author['self']['uri'],
                    'weight': 30,
                    'start': None,
                    'end': None
                }])
                df = pd.concat([df, row], ignore_inde=True)

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
                row = pd.DataFrame([{
                    'fname': fname,
                    'lname': lname,
                    'orcid': orcid,
                    'uri': uri,
                    'weight': wght,
                    'start': start,
                    'end': end
                }])
                df = pd.concat([df, row], ignore_index=True)

        if 'HFD' in station_url:
            row = pd.DataFrame([{
                'fname': 'Chris',
                'lname': 'Rennick',
                'orcid': '0000-0003-4993-0156',
                'uri': 'http://meta.icos-cp.eu/resources/people/chris_rennick',
                'weight': 100,
                'start': None,
                'end': None
            }])
            df = df.concat([df, row], ignore_inde=True)
        if 'ZOT' in station_url:
            row = pd.DataFrame([{
                'fname': 'Sönke',
                'lname': 'Zähle',
                'orcid': '0000-0001-5602-7956',
                'uri': 'http://meta.icos-cp.eu/resources/people/S%C3%B6nke_Zaehle',
                'weight': 100,
                'start': None,
                'end': None
            }])
            df = df.concat([df, row], ignore_inde=True)
        if c.debug:
            with open(df_pkl_path, 'wb') as f:
                pickle.dump(df, f)
            with open(json_pkl_path, 'wb') as f:
                pickle.dump(info, f)
        return df, info


def get_icos_ts(dobj_list: list = None, hgh: int = None,
                download: bool = False):

    time_start_l2 = dt.datetime.now()
    time_end_l2 = dt.datetime.now()

    data_df_ls = []
    data_lx_df = pd.DataFrame()

    for rdo in dobj_list:
        do = Dobj(rdo)
        fast = False
        spec = do.meta['specification']['self']['uri']
        level = int(do.meta['specification']['dataLevel'])
        if level == 2:
            if 'L2DataObject' in spec:
                # Get date & time for 1st & last observation:
                time_start_l2 = dt.datetime.strptime(do.meta['specificInfo']['acquisition']['interval']['start'], '%Y-%m-%dT%H:%M:%SZ')
                time_end_l2 = dt.datetime.strptime(do.meta['specificInfo']['acquisition']['interval']['stop'], '%Y-%m-%dT%H:%M:%SZ')
                level = 3
            else:
                level = 0
        else:
            if level == 1:
                if 'FastTrack' in spec:
                    time_end_fast = dt.datetime.strptime(do.meta['specificInfo']['acquisition']['interval']['stop'], '%Y-%m-%dT%H:%M:%SZ')
                    level = 2

    for rdo in dobj_list:
        do = Dobj(rdo)
        spec = do.meta['specification']['self']['uri']
        level = do.meta['specification']['dataLevel']
        project = do.meta['specification']['project']['self']['label']
        # print(spec)
        if level == 2:
            if 'L2DataObject' in spec:
                level = 3
            else:
                level = 0
        if level == 1:
            if 'FastTrack' in spec:
                fast = True
                level = 2

        # Get pandas dataframe
        if download:
            obs_data_df = get_icos_atm_product(dobj=do, level=level)
        else:
            obs_data_df = do.getColumns()
            obs_data_df['Datetime'] = pd.to_datetime(obs_data_df['TIMESTAMP'])
            obs_data_df = obs_data_df.set_index('Datetime')
        # Check if dobj corresponds to NRT data product:
        if level == 1:
            # Filter dataframe by quality flag value:
            if fast:
                obs_data_df = obs_data_df[time_end_l2:]
            else:
                if c.gas == 'n2o' and obs_data_df.Site.to_list()[0] in ['HTM', 'SVB']:
                    print(f'*******Passing', obs_data_df.Site.to_list()[0])
                else:
                    obs_data_df = obs_data_df[time_end_fast:]
            if c.useflags:
                obs_data_df = obs_data_df.loc[obs_data_df.Flag == 'U']
        else:
            if level == 0:
                # Filter dataframe by quality flag value and only values before L2 data start:
                time_start_l0 = dt.datetime.strptime(
                    do.meta['specificInfo']['acquisition']['interval'][
                        'start'], '%Y-%m-%dT%H:%M:%SZ')
                time_end_l2 = dt.datetime.strptime(
                    do.meta['specificInfo']['acquisition']['interval']['stop'],
                    '%Y-%m-%dT%H:%M:%SZ')
                obs_data_df = obs_data_df.query('Datetime < @time_start_l2')
            if c.useflags:
                obs_data_df = obs_data_df[obs_data_df['Flag'].isin(['O', 'U'])]

            # Add data dataframe of the current data object ID to the list:
        if level == 3:
            obs_data_df['Level'] = 2
        elif level == 2:
            obs_data_df['Level'] = 15
        elif level == 1:
            obs_data_df['Level'] = 1

        if (level == 0) & (len(obs_data_df) > 1):
            obs_data_df['Level'] = 0
            obs_data_df.loc[(obs_data_df.index >= time_start_l2) & (
                        obs_data_df.index <= time_end_l2), 'Level'] = 2

        data_df_ls.append(obs_data_df)
        contrib, info = get_roles(f_pid=do.id)
        c.file_contribs = pd.concat([contrib, c.file_contribs])

    # Concatenate list of dataframes to one dataframe:
    data_lx_df = pd.concat(data_df_ls)

    # Sort the dataframe index in ascending order:
    data_lx_df.sort_index(inplace=True)

    # Change column name from "co2" to "Meas":
    data_lx_df.rename({'co2': 'Meas'}, axis='columns', inplace=True)

    # if needed add column with Julian Year:
    if 'JulDate' not in data_lx_df:
        data_lx_df['JulDate'] = [toYearFraction(i) for i in data_lx_df.index]

    # if present drop column TIMESTAMP:
    if 'TIMESTAMP' in data_lx_df:
        data_lx_df.drop('TIMESTAMP', axis=1, inplace=True)

    # Return dataframe:
    return data_lx_df


def get_icos_atm_product(dobj: Dobj = None, level: int = None):
    """
    Get ICOS atmospheric data.

    Download ICOS ATM data by directly accessing the data objects from
    the Carbon Portal; this will trigger the download count for each
    object, unless we are on the blocklist.
    """

    def readfile(source: Path | IO[bytes] = None) -> pd.DataFrame:
        # Read the ICOS data object by using the io-stream handle and parse as csv
        # using the predefined column definitions and length of header.
        # Reading this column definitions from the io-stream directly needs seek to work and that fails,
        # so this part is commented out
        #        for i in range(0,45):
        #            header = f.readline()
        #            print(header)
        #        head=str(header)[3:-3]
        #        colnames="['"+head.replace(';',"','")+"']"
        #        nrcols=colnames.count(',')+1
        #        print(nrcols)
        #        print('Columns: ', colnames)
        #        f.seek(0)
        #        df = pd.read_csv(f,skiprows=skip[level],header=None,names=colnames[level],delimiter=';',usecols=range(0,nrcols[level]-1))
        if c.debug:
            pass
            # print('File name: ', f_name)
            # print('Level: ', level)
            # print('Columns: ', colnames[level])
            # print('Cols : ', nrcols[level])
        # Todo: To prevent pandas from guessing column types, pass these
        #  dtypes to the next read_csv(dtype=dtypes) call.
        # dtypes = {"Site": "object",  "SamplingHeight": "int64", "Year": "int64", "Month": "int64",
        #           "Day": "int64", "Hour": "int64", "Minute": "int64", "DecimalDate": "float64",
        #           "co2": "float64", "Stdev": "float64", "NbPoints": "int64", "Flag": "object",
        #           "InstrumentId": "int64", "QualityId": "int64", "LTR": "float64", "CMR": "float64",
        #           "STTB": "float64", "QcBias": "float64", "QcBiasUncertainty": "float64", "Origin": "object",
        #           "OriginalFlag": "object"}
        ret_df = pd.read_csv(source, comment='#', header=None, names=colnames[level], delimiter=';',
                             usecols=range(0, nrcols[level] - 1))
        return ret_df

    # modify the url to allow download by accepting the data license explicitly
    url = dobj.meta['accessUrl'].replace('https://data.icos-cp.eu/objects/',
                                         'https://data.icos-cp.eu/licence_accept?ids=%5B%22') + '%22%5D'
    # print('url:', url)

    # Get the data object from CP, unless we have the file in cache
    # already, if not, save it there.
    f_name = Path(c.zip, dobj.meta['fileName'])
    if not f_name.exists():
        r = requests.get(url, allow_redirects=True)
        with open(f_name, 'wb') as f:
            f.write(r.content)
        # print('filled cache with ', f_name)
    else:
        pass
        # print('hit cache for ', f_name)
    if f_name.suffix == '.zip':
        zf = zipfile.ZipFile(f_name, 'r')
        for item in zf.namelist():
            if c.debug:
                pass
                # print("File in zip: " + item)
        match = [s for s in zf.namelist() if 'ICOS_ATC' in s][0]
        df = readfile(source=zf.open(match))
    else:
        df = readfile(source=f_name)

    #    # access the url and open an io stream to it, if the file is zipped, unzip the stream, and pass the file to a dataframe
    #    r = requests.get(url, allow_redirects=True)
    #    if r.headers.get('content-type')=='application/zip':
    #        filename = r.content
    #        zf = zipfile.ZipFile(io.BytesIO(filename), 'r')
    #        for item in zf.namelist():
    #            if debug: print("File in zip: "+ item)
    #        match = [s for s in zf.namelist() if "ICOS_ATC" in s][0]
    #        df=readfile(zf.open(match))
    #    else:
    #        s=r.content
    #        df=readfile(io.StringIO(s.decode('utf-8')))

    # do some bookkeeping, like removing useless time columns, using a true datetime and indexing
    df.rename({'DecimalDate': 'JulDate'}, axis='columns', inplace=True)
    df['Datetime'] = [t2dt(i) for i in df['JulDate']]
    df = df.set_index('Datetime')
    df.drop(['Year', 'Month', 'Day', 'Hour', 'Minute'], axis=1, inplace=True)

    # if debug set printing of url and dataframe
    if c.debug:
        pass
        # print(url, ' ', df)

    return df


# Main program for producing obspack nc files from icos and non-icos
# timeseries of atmosphere data.
c = Config()
#init()
#process_obspack()
#run_all(process=True)

