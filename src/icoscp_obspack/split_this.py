# Standard library imports.
from pathlib import Path
from typing import IO, Any
import datetime as dt
import json
import numpy as np
import os
import pickle
import zipfile

# Related third party imports.
from icoscp.dobj import Dobj
from icoscp_core.icos import meta, ATMO_STATION
from requests.structures import CaseInsensitiveDict
import matplotlib.pyplot as plt
import netCDF4
import pandas as pd
import requests
import seaborn as sns
import xarray as xr

# Local application/library specific imports.
from icoscp_obspack import ccgfilt
from icoscp_obspack.config import Config
from icoscp_obspack.constants import envri as e
from icoscp_obspack.constants import queries as q
from icoscp_obspack.utils import progress_bar, t2dt, get_prev_by_name, get_hash_sum


# initialisation routine to set up global structures and initialise data
def init():
    global doi
    global atc_drought_header
    global atc_header
    global colnames
    global nrcols
    global skip
    global obspack_set
    global dfRoles
    global cntAll
    global useflags
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

    colnames = [atc_atmprod_header, atc_nrt_header, atc_fast_header,
                atc_l2_header]

    nrcols = [22, 18, 20, 20]
    skip = [45, 39, 45, 45]
    doi = 'XKKA-AWRS'
    obspack_set = {'doi_collection': 'https://doi.org/10.18160/' + doi,
                   'icos_class': [1, 2],
                   'non-icos': True,
                   'version': '11.1',
                   'contributors': [],
                   'contrib_ORCID': [],
                   'other': 'NA',
                   }
    cntAll = 0
    useflags = True
    get_mauna_loa()
    get_glb_avg_ch4()


def toYearFraction(date):

    def sinceEpoch(date): # returns seconds since epoch
        return time.mktime(date.timetuple())
    s = sinceEpoch

    year = date.year
    startOfThisYear = dt.datetime(year=year, month=1, day=1)
    startOfNextYear = dt.datetime(year=year+1, month=1, day=1)

    yearElapsed = s(date) - s(startOfThisYear)
    yearDuration = s(startOfNextYear) - s(startOfThisYear)
    fraction = yearElapsed/yearDuration

    return date.year + fraction


# look up station uri in dataset meta info and harvest contributor info for that station into a dataframe
def getStationRolesFromFilePid(fpid, debug=False):
    import json, requests
    from requests.structures import CaseInsensitiveDict

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


def generate_plot(df, back, meas, mlo, meas_name: str = None, unit: str = None, station: str = None,
                  png_file: Path = None, x_lim: list = None, y_lim: list = None):
    """Plot measurements, trend, smoothed curve."""
    l2 = meas.loc[meas.Level == 2]
    ax1 = l2.plot(x='JulDate', y='Meas', fontsize=12, label=station+' L2', linewidth=0, color='green',
                  marker='+', markersize=4, figsize=(15, 8))
    l15 = meas.loc[meas.Level == 15]
    l15.plot(ax=ax1, x='JulDate', y='Meas', label=station+' L1.5', linewidth=0, color='olive', marker='+',
             markersize=4, figsize=(15, 8))
    l1 = meas.loc[meas.Level == 1]
    l1.plot(ax=ax1, x='JulDate', y='Meas', linewidth=0, color='red', marker='+', markersize=4,
            label=station+' NRT')
    l0 = meas.loc[meas.Level == 0]
    l0.plot(ax=ax1, x='JulDate', y='Meas', linewidth=0, color='lightgreen', marker='+', markersize=4,
            label=station+' Hist.')
    ax1.set_facecolor('whitesmoke')
    plt.ylabel(meas_name+' '+unit, fontsize=14)
    sns.set_style("white")
    df.plot(y='Trend', ax=ax1, color='black', label='Trend from '+station)
    if not back.empty:
        back.plot(y='Trend', ax=ax1, color='yellow', linestyle="--", label='Global trend')
    mlo.plot(x='JulDate', y='Meas', ax=ax1, linewidth=0, color='red', marker='+', markersize=3,
             label='Global av.')
    h1, l1 = ax1.get_legend_handles_labels()
    # Remove the top right second legend.
    ax1.get_legend().remove()
    plt.xticks(np.arange(x_lim[0], x_lim[1], step=1))
    ax1.set_title(meas_name+' at '+station+'; measurements, trend and seasonal signal', fontsize=18)
    df.SmoothCurve.plot(ax=ax1, fontsize=12, color='blue', label='Smoothed curve '+station)
    ax1.set_xlabel('Year', fontsize=14)
    ax1.grid(zorder=0, linestyle='-.', color='grey')
    plt.legend(h1, l1, loc=2)
    plt.xlim(x_lim)
    plt.ylim(y_lim)
    if png_file is not None and c.do_png:
        plt.savefig(png_file, dpi=150)
    if c.plot:
        plt.show(close=True)
    plt.close()


def create_txt_header(
        obs_name: str = None,
        nc_file: Path = None,
        doi_cite: str = None,
        cit: str = ''
) -> list:

    head = []
    with open(c.header) as f:
        pre = f.readlines()
    stream = os.popen('ncdump -h ' + str(nc_file.resolve()))
    output = stream.readlines()
    filtered = []
    variables = ['#', '# ------------------------------------------------------------->>>>',
                 '# VARIABLE ATTRIBUTES', '#']
    for i in output:
        if '\t\t' in i:
            i = i.replace(' ;\n', '')
            i = i.replace('"', '')
            if '\t\t:' in i:
                i = i.replace('\t\t:', '# ')
                filtered.append(i)
            else:
                i = i.replace('\t\t', '# ')
                variables.append(i)
    variables.append('#')
    variables.append('# VARIABLE ORDER')
    variables.append('#')
    h_len = len(filtered) + len(variables) + len(pre) + 1

    fname = os.path.basename(nc_file)
    (dataset, sep, ext) = fname.rpartition('.')
    head.append('# header_lines : ' + str(h_len))
    if cit == '':
        cit = doi_citation(doi_id=f'10.18160/{doi_cite}')
    for i in pre:
        i = i.replace('\n', '')
        if 'doi_xxx' in i:
            i = i.replace('doi_xxx', doi_cite)
        if 'citation_xxx' in i:
            i = i.replace('citation_xxx', cit)
        if 'obspack_xxx' in i:
            i = i.replace('obspack_xxx', obs_name)
        if 'dataset_xxx' in i:
            i = i.replace('dataset_xxx', dataset)
        head.append(i)
    for i in filtered:
        head.append(i)
    for i in variables:
        head.append(i)
    return head

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
    response = requests.get(uri,headers={"Accept": "application/json"})
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        # Print an error message
        print('Error fetching data')
        return('Error')


def process_obspack() -> pd.DataFrame:
    meta_info = get_file_meta()
    # First scan to determine all stations and files, collect
    # attribution metadata.
    # First run to collect citation data on contributors
    run_all(meta_info=meta_info, process=False)
    c.col_contribs = cleanup_author_list(contribs=c.col_contribs)

    # Save contributor and author info as json for the DOI minting.
    auth = Path(c.output, f'authors_{c.gas}.json')
    contribs = Path(c.output, f'contributors_{c.gas}.json')
    with open(auth, 'w') as file_handle:
        file_handle.write(citation(as_contrib=False))
    with open(contribs, 'w') as file_handle:
        file_handle.write(citation(as_contrib=True))
    return meta_info


def cleanup_author_list(contribs: pd.DataFrame = None) -> pd.DataFrame:
    # Drop duplicates in the author list.
    contribs = contribs.sort_values('lname', ascending=False).\
        drop_duplicates(subset=['fname', 'lname'])
    contribs.loc[contribs['weight'].isnull(), 'weight'] = 0
    contribs['wght'] = 100 - contribs.weight.astype(int)
    contribs = contribs.sort_values(by=['wght', 'lname'], ascending=True)
    return contribs


def get_file_meta() -> pd.DataFrame:
    info = pd.DataFrame()
    flist = get_file_list(get_specs())
    for pos, (_, file) in enumerate(flist.iterrows()):
        progress_bar(current=pos+1, total=len(flist))
        uri = file['dobj']
        data = new_file_info(uri)
        use_file = False
        for col in data['specificInfo']['columns']:
            if col['label'] == c.gas:
                use_file = True
        if use_file:
            row = pd.DataFrame([{
                'uri': uri,
                'fileName': data['fileName'],
                'stationId': data['specificInfo']['acquisition']['station']['id'],
                'hgh': data['specificInfo']['acquisition']['samplingHeight'],
                'level': data['specification']['dataLevel'],
                'specification': data['specification']['self']['uri']}])
            info = pd.concat([info, row], ignore_index=True)
    return info


def new_file_info(uri: str = None):
    response = requests.get(uri, headers={'Accept': 'application/json'})
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print('Error fetching data')
        return 'Error'



def get_specs() -> list[str]:
    """Return specifications given the gas type."""
    if c.gas == 'co2':
        # specs=['atcCo2Product','atcCo2NrtGrowingDataObject']
        # atcCo2Product repl drought2018AtmoProduct
        specs = ['atcCo2Product', 'atcCo2L2DataObject',
                 'atcGHGFastTrackNRTDataObject',
                 'atcCo2NrtGrowingDataObject']
        doi = '0HYS-FF7X'
    elif c.gas == 'ch4':
        # specs = ['atcCh4Product','atcCh4NrtGrowingDataObject']
        specs = ['atcCh4Product', 'atcCh4L2DataObject',
                 'atcGHGFastTrackNRTDataObject', 'atcCh4NrtGrowingDataObject']
        doi = 'FE8D-2APZ'
    elif c.gas == 'n2o':
        # specs = ['atcCh4Product','atcCh4NrtGrowingDataObject']
        specs = ['atcN2oProduct', 'atcN2oL2DataObject',
                 'atcGHGFastTrackNRTDataObject', 'atcN2oNrtGrowingDataObject']
        doi = 'XKKA-AWRS'
    elif c.gas == 'co':
        # specs = ['atcCh4Product','atcCh4NrtGrowingDataObject']
        specs = ['atcCoProduct', 'atcCoL2DataObject',
                 'atcGHGFastTrackNRTDataObject', 'atcCoNrtGrowingDataObject']
        doi = '6ZXD-BAAZ'
    else:
        raise "Can't handle this gas yet!"
    return specs


def get_file_list(specs: list = None) -> pd.DataFrame:
    """Query atmospheric data.

    Create and execute a sparql query to retrieve atmospheric data that
    we need to explore. By default, this function will query data files
    described by these specifications: 'atcCo2Product',
    'atcCo2L2DataObject', 'atcCo2NrtGrowingDataObject'.
    """
    if specs is None:
        specs = ['atcCo2Product', 'atcCo2L2DataObject', 'atcCo2NrtGrowingDataObject']
    anchor = ''
    for spec in specs:
        anchor += '<{pref}{spec}>'.format(
            pref=e.ICOS_CONFIG.meta_resources_prefix, spec=spec)
    with open(q.FILES_BY_SPEC, mode='r') as q_hdl:
        query = q_hdl.read().replace('#anchor', anchor)
    r = requests.get(e.ICOS_CONFIG.sparql,
                     params={'format': 'json', 'query': query})
    data = r.json()
    # Convert the result into a table where each row contains
    # information about the roles.
    data_ls = [[data['results']['bindings'][row].get(col, {}).get('value') for col in data['head']['vars']] for row in range(len(data['results']['bindings']))]

    return pd.DataFrame(data_ls, columns=data['head']['vars'])


def run_all(meta_info, process=False):

    prev = None
    def_citations = [doi_citation('10.18160/0F1E-DKXT'),
                     doi_citation('10.18160/ATM_NRT_CO2_CH4')]

    # Unique dataset nr in the obspack product.
    if c.gas == 'co2':
        nr = 1000
        fact = 1e6
        calib = 'WMO CO2 X2019'
    elif c.gas == 'ch4':
        nr = 2000
        fact = 1e9
        calib = 'WMO X2004A'
    elif c.gas == 'n2o':
        nr = 3000
        fact = 1e9
        calib = 'NOAA-2006A'
    elif c.gas == 'co':
        nr = 4000
        fact = 1e6
        calib = 'WMO X2014A'
    else:
        exit(f'Unknown or not implemented gas: {c.gas}.\nAborting...')

    stations = meta.list_stations(ATMO_STATION)
    for st in stations:
        # Only atmospheric stations
        station_meta = meta.get_station_meta(st.uri)
        st_id = st.id
        if st_id != prev:
            prev = st_id
            st_class = station_meta.specificInfo.stationClass
            data = meta_info[meta_info['stationId'] == st_id]

            # Look up the list of relevant data for these stations,
            # list of associated sampling heights and determine the
            # maximum sampling height.
            maxh = 0
            heights = []
            use_data = []
            for i, do in data.iterrows():
                if do.hgh is not None:
                    maxh = max(float(do.hgh), maxh)
                    if (st_id == 'HUN') and (abs(float(do.hgh) - 48.0) < 1):
                        heights.append(50)
                    else:
                        heights.append(float(do.hgh))
                else:
                    maxh = 0
                    heights.append(0.0)
            # Deduplicate the list of available sampling heights.
            hgh = [ii for n, ii in enumerate(heights) if ii not in heights[:n]]

            # now go through the sampling height of each station one by one
            # if st_id!='CRP':
            # if st_id=='HFD':
            # if True:
            if st_class in ['1', '2']:
                for h in hgh:
                    treat_data = []
                    citations = []
                    c.d_files = []
                    for i, do in data.iterrows():
                        if do.hgh is not None:
                            if abs(float(do.hgh) - h) < 2.5:
                                if (st_id == 'JFJ') and (
                                        abs(float(do.hgh) - 5.0) < 1):
                                    maxh = maxh
                                else:
                                    s = Dobj(do.uri)
                                    treat_data.append(do.uri)
                                    if st_id == 'HFD':
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
                        print(st_id, ' Height:', h, ' Class:', st_class,
                              ' NrFiles:', len(treat_data))
                        if process:
                            lab_nr = c.icos_stations[
                                c.icos_stations.Hist == st_id
                                ].NOAALabNr.values[0]
                            if len(hgh) > 1:
                                file_name = (
                                        c.gas + '_' + st_id.lower() +
                                        '_tower-insitu_' + str(int(lab_nr)) +
                                        '_allvalid-' + str(int(h)) + 'magl')
                            else:
                                file_name = (
                                        c.gas + '_' + st_id.lower() +
                                        '_surface-insitu_' + str(int(lab_nr)) +
                                        '_allvalid')
                            df = analyse_station(st_id=st_id, hgh=int(h),
                                                 dobj_list=treat_data,
                                                 f_name=file_name)

                            if not df.empty:
                                c.file_contribs = cleanup_author_list(c.file_contribs)
                                person = person_list()
                                try:
                                    write_nc(
                                        file_name, df, station_meta, citations,
                                        obspack_set, persons=person, hgh=h,
                                        calib_scale=calib, factor=fact,
                                        nc_cnt=nr, doi_cite=doi
                                    )
                                except e:
                                    print('Error writing: ', file_name)
                                    raise(e)

                                row = pd.DataFrame([{
                                    'fname': file_name,
                                    'folder': c.nc,
                                    'station': st_id,
                                    'hgh': h,
                                    'hash': '',
                                    'Handle': ''
                                }])
                                c.produced = pd.concat([c.produced, row], ignore_index=True)
                                c.produced.to_csv(Path(c.output, 'produced.csv'))
                                nr = nr + 1


def add_roles(pid: any = None):
    # Add contributors for file with this PID to the global contribs dataframes
    roles, info = get_roles(f_pid=pid)
    c.col_contribs = pd.concat([roles, c.col_contribs])
    return roles


# look up station uri in dataset meta info and harvest contributor info for that station into a dataframe
def get_roles(f_pid: any = None):
    if e.ICOS_CONFIG.station_prefix in f_pid:
        station_url = f_pid
    elif len(f_pid) < 7:
        station_url = e.ICOS_CONFIG.station_prefix + f_pid
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


def citation(as_contrib: bool = False) -> str:
    """Return the formatted citation json."""
    data_col = 'DataCollector' if as_contrib else ''
    data_cur = 'DataCurator' if as_contrib else ''
    data_dist = 'Distributor' if as_contrib else ''
    data_man = 'DataManager' if as_contrib else ''
    s = '"contributors": [' if as_contrib else '"creators": ['

    s = s + inst_dcite_json('ICOS RI', data_dist)
    for i, person in c.col_contribs.iterrows():
        if person['weight'] > 0:
            p_json = p_dcite_json(first_name=person['fname'],
                                  last_name=person['lname'],
                                  orcid=person['orcid'],
                                  contrib_type=data_col)
            s = s + ',' + p_json
    s = s + ',' + inst_dcite_json('ICOS Carbon Portal', data_cur)
    s = s + ',' + inst_dcite_json('ICOS Atmosphere Thematic Centre', data_man)
    s = s + ',' + inst_dcite_json('ICOS Flask And Calibration Laboratory', data_col)
    if as_contrib:
        s = s + ',' + inst_dcite_json('ICOS Flask And Calibration Laboratory', data_cur)
    s = s + ',' + inst_dcite_json('ICOS Central Radiocarbon Laboratory', data_cur)
    s = s + ' ]\n'
    return s


def inst_dcite_json(name: str = None, contrib_type: str = None) -> str:
    """Return the formatted institute datacite json."""
    s = '  {\n  "name" : {\n    "name" : "'+name+'",\n'
    s = s + '    "nameType" : "Organizational"\n  },\n'
    s = s + '  "affiliation" : [ ],\n'
    if contrib_type is not None:
        s = s + '  "contributorType" : "'+contrib_type+'",\n'
    s = s + '  "nameIdentifiers" : [ ]\n'
    s = s + '  }'
    return s


def p_dcite_json(first_name: str = None, last_name: str = None,
                 orcid: str = None, affiliation: str = None,
                 contrib_type: str = None) -> str:
    """Return the formatted person datacite json."""
    s = ('  {\n  "name" : {\n    "familyName" : "' + last_name + '",\n' +
         '    "givenName" : "' + first_name + '",\n' +
         '    "nameType" : "Personal"\n  },\n')
    if affiliation is not None:
        s = s + '  "affiliation" : "' + affiliation + '",\n'
    else:
        s = s + '  "affiliation" : [ ],\n'
    if contrib_type is not None:
        s = s + '  "contributorType" : "' + contrib_type + '",\n'
    if orcid is not None:
        s = (s + '  "nameIdentifiers" : [ {\n' + '    "nameIdentifier" : "' +
             orcid + '",\n    "scheme" : {\n')
        s = s + '      "nameIdentifierScheme" : "ORCID",\n'
        s = s + '      "schemeUri" : "http://orcid.org/"\n    } \n  } ]\n '
    else:
        s = s + '  "nameIdentifiers" : [ ]\n'
    s = s + '  }'
    return s


def get_mauna_loa() -> None:
    # Todo: do we have to read different trends for different gases?
    # Get the most recent Mauna Loa CO2 data.
    # Monthly marine BL global averages:
    # CH4: https://gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_mm_gl.txt
    # N2O: https://gml.noaa.gov/webdata/ccgg/trends/n2o/n2o_mm_gl.txt

    mauna_loa = pd.read_csv(
        'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_weekly_mlo.txt',
        skiprows=37, header=None, names=['JulDate', 'Meas'], delimiter=r'\s+',
        usecols=[3, 4])
    mauna_loa = mauna_loa.query('Meas>20').copy()
    mauna_loa['DateTime'] = mauna_loa['JulDate'].apply(t2dt)
    mauna_loa.set_index('DateTime', inplace=True)
    mauna_loa.to_csv(c.mauna_loa)
    ml = ghg_filter_ts(mauna_loa.JulDate, mauna_loa.Meas) if c.analyse \
        else pd.DataFrame()
    ml.to_csv(c.ml)
    return


def ghg_filter_ts(time, meas, shortTerm=80, longTerm=667, numPolyterms=3,
                  numHarmonics=4, timeZero=2010, sampleInterval=1/24) \
        -> pd.DataFrame:
    """Function wrapper to the CCGCRV routine from Thonen et al. (1996)

    Filters a timeseries by smoothing and removing higher frequency
    information and fitting a trend and harmonic oscillation.
    Specifically, designed for greenhouse gas observations.
    The input parameters are further described in ccgfilt.py, under the
    ccgFilter class.

    Input
    Observational data provided in Pandas dataframe with index datetime
    as YYYY.fraction and the observation series in the first column.

    Result
    A dataframe with index datetime containing in the columns the
    GrowthRate, Function, Poly, SmoothCurve, Trend, Cycle, Residual,
    Detrended the interpolated sampleInterval
    """

    gap = 0
    debug = True
    filt = ccgfilt.ccgFilter(time, meas, shortTerm, longTerm, sampleInterval,
                             numPolyterms, numHarmonics, timeZero, gap, debug)

    # Get x,y data for plotting
    x0 = filt.xinterp
    y1 = filt.getFunctionValue(x0)
    y2 = filt.getPolyValue(x0)
    y3 = filt.getSmoothValue(x0)
    y4 = filt.getTrendValue(x0)
    y5 = y3 - y4

    # Seasonal Cycle
    # x and y are original data points
    trend = filt.getTrendValue(time)
    detrend = meas - trend
    harmonics = filt.getHarmonicValue(x0)
    smooth_cycle = harmonics + filt.smooth - filt.trend
    # residuals from the function
    resid_from_func = filt.resid
    # smoothed residuals
    resid_smooth = filt.smooth
    # trend of residuals
    resid_trend = filt.trend
    # residuals about the smoothed line
    resid_from_smooth = filt.yp - filt.getSmoothValue(meas.index)
    deriv = filt.deriv

    return pd.DataFrame({'GrowthRate': deriv, 'Function': y1, 'Poly': y2,
                         'SmoothCurve': y3, 'Trend': y4, 'Cycle': smooth_cycle,
                         'Residual': resid_trend, 'Detrended': y5},
                        index=pd.Index(x0, name='datetime'))


def get_glb_avg_ch4() -> None:
    # Todo: do we have to read different trends for different gases?
    mauna_loa_ch4 = pd.read_csv(
        'https://gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_mm_gl.txt',
        skiprows=65, header=None, names=['JulDate', 'Meas'], delimiter=r'\s+',
        usecols=[2, 3]
    )
    mauna_loa_ch4 = mauna_loa_ch4.query('Meas>20').copy()
    mauna_loa_ch4['DateTime'] = mauna_loa_ch4['JulDate'].apply(t2dt)
    mauna_loa_ch4.set_index('DateTime', inplace=True)
    mauna_loa_ch4.to_csv(c.glb_avg_ch4)
    return


def doi_citation(doi_id: str = None, citation_style: str = 'elsevier-harvard') \
        -> str:
    headers = CaseInsensitiveDict()
    headers['Accept'] = 'text/x-bibliography; style=' + citation_style
    resp = requests.get('https://doi.org/'+doi_id, headers=headers)
    return resp.text if resp.status_code == 200 else 'citation not found'


def analyse_station(
        st_id: str = None,
        hgh: int = None,
        dobj_list: list = None,
        f_name: str = None
) -> pd.DataFrame:
    """Run ccgfilt for Mauna Loa and the chosen station."""
    icos_df = get_icos_ts(dobj_list=dobj_list, hgh=hgh, download=True)
    if icos_df.empty:
        print('No data found for station ' + st_id + ' ' + str(hgh))
    else:
        if c.do_png:
            f_name = Path(c.png, f_name)
            try:
                df = ghg_filter_ts(icos_df.JulDate, icos_df.Meas)
                mau = pd.DataFrame()
                back = pd.DataFrame()
                gas_name = ''
                if c.gas == 'co2':
                    gas_name = 'CO${_2}$'
                    unit = '[µmol/mol]'
                    limy = [380, 460]
                    back = pd.read_csv(c.ml)
                    mau = pd.read_csv(c.mauna_loa)
                elif c.gas == 'ch4':
                    gas_name = 'CH${_4}$'
                    unit = '[nmol/mol]'
                    limy = [1800, 2500]
                    mau = c.glob_aver
                elif c.gas == 'n2o':
                    gas_name = 'N${_2}$O'
                    unit = '[nmol/mol]'
                    limy = [315, 370]
                    mau = c.glob_aver
                else:
                    exit(f'Unknown or not implemented gas: {c.gas}.\nAborting...')

                generate_plot(df, back, icos_df, mau, meas_name=gas_name, unit=unit,
                              station=f'{st_id} {str(hgh)}', png_file=f_name, x_lim=[2010, 2025.1],
                              y_lim=limy)
            except (AttributeError, KeyError, TypeError, ValueError, FileNotFoundError, OSError, NameError,
                    IndexError) as plot_exception:
                print(f'Error in time filtering for station {st_id}; plot skipped due to: {plot_exception}')
    return icos_df


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

        print(obs_data_df.Site.to_list()[0])
        # Check if dobj corresponds to NRT data product:
        if level == 1:
            # Filter dataframe by quality flag value:
            obs_data_df.to_csv('zois.csv')
            if fast:
                obs_data_df = obs_data_df[time_end_l2:]
            else:
                if obs_data_df.Site.to_list()[0] == 'SVB':
                    print(f'*******Passing', obs_data_df.Site.to_list()[0])
                else:
                    obs_data_df = obs_data_df[time_end_fast:]
            if useflags:
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
            if useflags:
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


def glob_average() -> pd.DataFrame:
    skip_rows = 58 if c.gas == 'co2' else 65
    url = f'https://gml.noaa.gov/webdata/ccgg/trends/{c.gas}/{c.gas}_mm_gl.txt'
    global_aver = pd.read_csv(url, skiprows=skip_rows, header=None,
                              names=['JulDate', 'Meas', 'Trend'],
                              delimiter=r"\s+", usecols=[2, 3, 5])
    global_aver = global_aver.query('Meas>20')
    global_aver['DateTime'] = [t2dt(i) for i in global_aver.JulDate]
    global_aver.set_index('DateTime', inplace=True)
    return global_aver


def get_icos_atm_product(dobj: Dobj = None, level: int = None):
    """
    Get ICOS atmospheric data.

    Download ICOS ATM data by directly accessing the data objects from
    the Carbon Portal; this will trigger the download count for each
    object, unless we are on the blocklist.
    """
    def count(s, ch):
        """Count occurrences of a character in a string."""
        cnt = 0
        for i in s:
            if i == ch:
                cnt += 1
        return cnt

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
        #        nrcols=count(colnames,',')+1
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
        ret_df = pd.read_csv(source, comment='#', header=None,
                             names=colnames[level], delimiter=';',
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
        print('hit cache for ', f_name)
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


def person_list():
    name_list = ''
    first = True
    for i, p in c.col_contribs.iterrows():
        if not first:
            name_list = name_list + ' AND '
        first = False
        name_list = name_list + p.fname + ' ' + p.lname
    return name_list


def write_nc(f_name, df, station, citations, settings, persons='', hgh=150,
             factor=1e6, calib_scale='WMO CO2 X2019', lab_id=466, nc_cnt=0,
             doi_cite='PEKQ-M4T1'):
    """Write measurements' data as ObsPack NetCDF file."""

    global cntAll

    # for testing purposes you can truncate a data file to max 100 rows
    # df = df[:99]

    dlen = len(df.index)
    nc_name = Path(c.nc, f'{f_name}.nc')
    ds = netCDF4.Dataset(nc_name, 'w', format='NETCDF4', clobber=True)
    #    try:
    # create dimensions
    time = ds.createDimension('time', dlen)
    s20 = ds.createDimension('string_of_20chars', 20)
    cal_6 = ds.createDimension('calendar_components', 6)
    s10 = ds.createDimension('string_of_10chars', 10)
    s200 = ds.createDimension('string_of_200chars', 200)
    dim6 = ds.createDimension('dim_concerns', 6)
    mip17 = ds.createDimension('mip_nmodels', 17)
    ch40 = ds.createDimension('nchar', 40)

    # add variables
    time = ds.createVariable('time', 'i4', ('time',), zlib=True)
    time.standard_name = 'time'
    time.longname = 'sample_time_in_seconds_since_january_1_1970'
    time.units = 'seconds since 1970-01-01T00:00:00Z'
    time.comment = 'POSIX time.  Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported' \
                   ' at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                   ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    # add variables
    start_time = ds.createVariable('start_time', 'i4', ('time',), zlib=True)
    start_time.longname = 'sample_time_in_seconds_since_january_1_1970'
    start_time.units = 'seconds since 1970-01-01T00:00:00Z'
    start_time.comment = 'POSIX time.  Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported' \
                         ' at the beginning of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                         ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    datetime = ds.createVariable('datetime', 'c',
                                 ('time', 'string_of_20chars',), zlib=True)
    datetime.longname = 'air_sample_date_and_time_in_UTC'
    datetime.comment = 'Air sample date and time in UTC ISO 8601 format. Time-averaged values are reported at' \
                       ' the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                       ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    time_decimal = ds.createVariable('time_decimal', 'f8', ('time',),
                                     zlib=True)
    time_decimal.longname = 'sample_decimal_year_in_UTC'
    time_decimal.comment = 'Decimal year in UTC. Time-averaged values are reported at the midpoint of the averaging ' \
                           'interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the nearest second.'

    time_components = ds.createVariable('time_components', 'i2',
                                        ('time', 'calendar_components',),
                                        fill_value=-9, zlib=True)
    time_components.longname = 'integer_components_of_UTC_date/time'
    time_components.order = 'year, month, day, hour, minute, second'
    time_components.comment = 'Calendar time components as integers.  Times and dates are UTC. Time-averaged values are ' \
                              'reported at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to ' \
                              'the nearest second.'

    solartime_components = ds.createVariable('solartime_components', 'i2',
                                             ('time', 'calendar_components',),
                                             fill_value=-9, zlib=True)
    solartime_components.longname = 'integer_components_of_local_solar_date/time'
    solartime_components.order = 'year, month, day, hour, minute, second'
    solartime_components.comment = 'Calendar local solar time components as integers.  UTC time is converted to local solar ' \
                                   'time based on longitude and day-of-year.  Time-averaged values are ' \
                                   'reported at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to ' \
                                   'the nearest second.'

    value = ds.createVariable('value', 'f4', ('time',), fill_value=np.nan,
                              zlib=True)
    value.long_name = 'measured_mole_fraction_of_trace_gas_in_dry_air'
    value.standard_name = 'mole_fraction_of_' + c.gas + '_in_dry_air'
    value.units = 'mol mol-1'
    value.comment = 'mole per mole of dry air'
    value.scale_comment = calib_scale

    nvalue = ds.createVariable('nvalue', 'i', ('time',), fill_value=-9,
                               zlib=True)
    nvalue.long_name = 'number_of_measurements_contributing_to_reported_value'
    nvalue.comment = 'Number of individual measurements used to compute reported value. See provider_comment' \
                     ' if available.'

    value_std_dev = ds.createVariable('value_std_dev', 'f4', ('time',),
                                      fill_value=np.nan, zlib=True)
    value_std_dev.long_name = 'standard_deviation_in_reported_value'
    value_std_dev.units = 'mol mol-1'
    value_std_dev.comment = 'This is the standard deviation of the reported mean value when nvalue is greater than 1' \
                            '. See provider_comment if available.'

    latitude = ds.createVariable('latitude', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    latitude.long_name = 'sample_latitude_in_decimal_degrees'
    latitude.units = 'decimal degrees north (-90..90)'
    latitude.comment = 'Latitude at which air sample was collected.'

    longitude = ds.createVariable('longitude', 'f4', ('time',),
                                  fill_value=np.nan, zlib=True)
    longitude.long_name = 'sample_longitude_in_decimal_degrees'
    longitude.units = 'decimal degrees east (-180..180)'
    longitude.comment = 'Longitude at which air sample was collected.'

    altitude = ds.createVariable('altitude', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    altitude.long_name = 'sample_altitude_in_meters_above_sea_level'
    altitude.units = 'meters above sea level (masl)'
    altitude.comment = 'Altitude (surface elevation plus sample intake height) at which air sample was collected'

    intake_height = ds.createVariable('intake_height', 'f4', ('time',),
                                      fill_value=np.nan, zlib=True)
    intake_height.long_name = 'Height above ground at which air sample was collected'
    intake_height.units = 'meters above ground level (magl)'
    intake_height.comment = 'Sample intake height in meters above ground level (magl)'

    qc_flag = ds.createVariable('qc_flag', 'c', ('time',), fill_value='-',
                                zlib=True)
    qc_flag.long_name = 'quality_control_flag'
    qc_flag.comment = '- Flag U = data correct before manual quality control - Flag O = data correct ' \
                      'after manual quality control, other flags denote incorrect data. ' \
                      'Data processing at ICOS ATC is described in [Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    quality_id = ds.createVariable('quality_id', 'i', ('time',), fill_value=-9,
                                   zlib=True)
    quality_id.long_name = 'quality_id'
    quality_id.comment = 'unique id linking to the QC provenance - Data processing at ICOS ATC is described in ' \
                         '[Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    instrument = ds.createVariable('instrument', 'i', ('time',), fill_value=-9,
                                   zlib=True)
    instrument.long_name = 'instrument_ID_to_detect_atmospheric_parameter'
    instrument.comment = 'Instrument ID used to detect atmospheric parameter. See provider_comment if available.'
    instrument.provider_comment = 'This variable is the ICOS provided Instrument ID'

    icos_datalevel = ds.createVariable('icos_datalevel', 'b', ('time',),
                                       fill_value='255', zlib=True)
    icos_datalevel.long_name = 'icos_data_release_level'
    icos_datalevel.comment = 'Level 0 means pre-ICOS or non-ICOS data (processing by PI); Level 1 means NRT=' \
                             'near real-time data (Automatic Quality Control by ICOS ATC) delay max 24 hrs; Level 2 means final ' \
                             'quality data (Manual and automatic QC by PI and ATC - Data processing at ICOS ATC is described in ' \
                             '[Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    icos_LTR = ds.createVariable('icos_LTR', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    icos_LTR.long_name = 'icos_long_term_repeatability'
    icos_LTR.units = 'mol mol-1'
    icos_LTR.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                       '2015] https://doi.org/10.5194/amt-8-3867-2015'

    icos_CMR = ds.createVariable('icos_SMR', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    icos_CMR.long_name = 'icos_continuous_measurement_repeatability'
    icos_CMR.units = 'mol mol-1'
    icos_CMR.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                       '2015] https://doi.org/10.5194/amt-8-3867-2015'

    icos_STTB = ds.createVariable('icos_STTB', 'f4', ('time',),
                                  fill_value=np.nan, zlib=True)
    icos_STTB.long_name = 'icos_short_term_target_bias'
    icos_STTB.units = 'mol mol-1'
    icos_STTB.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                        '2015] https://doi.org/10.5194/amt-8-3867-2015'

    obs_flag = ds.createVariable('obs_flag', 'b', ('time',), fill_value=1,
                                 zlib=True)
    obs_flag.long_name = 'obs_flag';
    obs_flag.units = 'binary';
    obs_flag.comment = 'Determined by data provider (1: large spatial scale representation; 0: ' \
                       'local/regional influence).  The implementation of this flag is still being developed.'

    obspack_id = ds.createVariable('obspack_id', 'c',
                                   ('time', 'string_of_200chars',), zlib=True)
    obspack_id.long_name = 'obs_flag';
    obspack_id.comment = 'Unique identification string that distinguishes the data item from all other data items ' \
                         'both within an ObsPack product, and across any ObsPack data product. It includes obspack_name, ' \
                         'dataset_name, and obspack_num, with each field delimited by a tilde (~).'

    assimilation_concerns = ds.createVariable('assimilation_concerns', 'b',
                                              ('time', 'dim_concerns'),
                                              zlib=True)
    assimilation_concerns.long_name = 'assimilation_concerns'
    assimilation_concerns.units = 'NA'
    assimilation_concerns.order = 'time window, representivity, variability, under review, wdcgg-background, ' \
                                  'scale_conversion'
    assimilation_concerns.comment = 'Values in this array indicate if the given observation has the assimilation ' \
                                    'concern defined by each column. A value of 0 means that there is no concern or it is not known to exist, ' \
                                    'and a non-zero value means that this concern does exist. Data suitable for a global scale model in ' \
                                    'general will have a 0 in the time window, representivity, and variability columns of this variable. The' \
                                    'implementation of this variable is still being developed.'

    obs_num = ds.createVariable('obs_num', 'i', ('time',), zlib=True)
    obs_num.long_name = 'unique_dataset_observation_number'
    obs_num.comment = 'Unique observation number in this data set.  Range is from 1 to ' + str(
        len(df) + 1)

    obspack_num = ds.createVariable('obspack_num', 'i', ('time',), zlib=True)
    obspack_num.long_name = 'unique_ObsPack_observation_number'
    obspack_num.comment = 'Unique observation index number across all data sets in the ObsPack data product. ' \
                          'Range is from 1 to max_obspack_num'

    # fill the attributes, most value are default and copied from Obspack V7 2021 and some need to be replaced
    # with actual info before writing to netcdf
    obspack_name = 'obspack_' + c.gas + '_' + str(
        lab_id) + '_GV_ICOSFT2025.1_' + dt.datetime.now().strftime('%Y%m%d')

    s = c.icos_stations[c.icos_stations.Hist == station.id]
    lab_id = s.NOAALabNr.values[0]
    lab_name = s.NOAA_Lab_name.values[0]
    TZ = s.Timezone.values[0]
    if s.ICOS_L12.values[0] == '':
        isICOS = 'No'
    else:
        isICOS = 'Yes'
    oscarId = s.OSCAR_ID.values[0]
    if oscarId == '':
        oscarId = 'n.a.'

    # now finally time to start writing the data arrays!
    def rndts(dat, offsetSec=0):
        return round(dat.to_pydatetime().timestamp() + offsetSec)

    tim = [rndts(i, 1800.0) for i in df.index]
    time[:] = tim

    timstart = [rndts(i) for i in df.index]
    start_time[:] = timstart

    def toiso(dat, offsetSec=0):
        dat = dat + dt.timedelta(seconds=offsetSec)
        return dat.isoformat() + 'Z'

    isof = [toiso(i, 1800) for i in df.index]
    iso = netCDF4.stringtochar(np.array(isof, dtype='S20'))
    datetime[:] = iso

    def year_frac(dat, offsetSec=0):
        dat = dat + dt.timedelta(seconds=offsetSec)
        start = dt.datetime(dat.year, 1, 1, 0, 0, 0)
        endyr = dt.datetime(dat.year + 1, 1, 1, 0, 0, 0)
        yearlen = dt.datetime.timestamp(endyr) - dt.datetime.timestamp(start)
        year_frac = (dt.datetime.timestamp(dat) - dt.datetime.timestamp(
            start)) / yearlen
        return dat.year + year_frac

    timdec = [year_frac(i, 1801.1) for i in df.index]
    time_decimal[:] = timdec

    timeseries_start = df.index[0].isoformat() + 'Z'
    timeseries_end = df.index[len(df) - 1].isoformat() + 'Z'

    def tocomp(dat, OffsetSec=0):
        dat = dat + dt.timedelta(seconds=OffsetSec)
        return [dat.year, dat.month, dat.day, dat.hour, dat.minute, 0]

    timcomp = [tocomp(i, 1801.1) for i in df.index]
    time_components[:] = timcomp

    timcomp = [tocomp(i, 1800.0 + TZ * 3600.0) for i in df.index]
    solartime_components[:] = timcomp

    def scaleAndMask(dff, col, fact=1):
        dff[col] = dff[col] / fact
        dff.loc[(dff[col] < 0), col] = np.nan
        return dff[col]

    value[:] = scaleAndMask(df, 'Meas', factor)
    value_std_dev[:] = scaleAndMask(df, 'Stdev', factor)
    nvalue[:] = df.NbPoints
    latitude[:] = station.location.lat
    longitude[:] = station.location.lon
    altitude[:] = float(station.location.alt) + hgh
    intake_height[:] = hgh
    qc_flag[:] = df.Flag
    icos_datalevel[:] = df.Level
    try:
        icos_LTR[:] = scaleAndMask(df, 'LTR', factor)
        icos_CMR[:] = scaleAndMask(df, 'CMR', factor)
        icos_STTB[:] = scaleAndMask(df, 'STTB', factor)
    except:
        icos_LTR[:] = np.nan
        icos_CMR[:] = np.nan
        icos_STTB[:] = np.nan
    quality_id[:] = df.QualityId
    try:
        instrument[:] = df.InstrumentId
    except:
        instrument[:] = -1
    obs_flag[:] = 1
    obs_num[:] = np.arange(1, len(df) + 1, 1)
    obspack_num[:] = np.arange(cntAll + 1, cntAll + len(df) + 1, 1)
    ss = np.array(
        [obspack_name + '~' + f_name + '~' + str(cntAll + i + 1) for i in
         range(len(df))], dtype='S200')
    obspack_id[:] = netCDF4.stringtochar(ss)

    assimilation_concerns[:, :] = 0

    if c.gas == 'co2':
        warning = 'In Feb 2021, NOAA updated the WMO CO2 scale from version X2007 to X2019 ' \
                  '(Hall et al., 2021). The X2019 scale supersedes all previous versions of the WMO scale and is ' \
                  'used in this GV+ release. Values contributed on scales other than X2019 have been adjusted by ' \
                  'either known scale offsets or with the known X2019 to X2007 relationship to account for changes ' \
                  'in the scale relationship caused by the X2019 revision.'
    else:
        warning = ''

    attr = {'site_code': station.id,
            'site_name': station.org.name,
            # python quirk. station.name returns the name of the station object
            'site_country': station.countryCode,
            'site_latitude': station.location.lat,
            'site_longitude': station.location.lon,
            'site_elevation': station.location.alt,
            'site_elevation_unit': 'masl',
            'site_position_comment': 'This is the nominal location of the site. The sampling location at many sites' \
                                     ' has changed over time, and we report here the most recent nominal location. The actual sampling location' \
                                     ' for each observation is not necessarily the site location. The sampling locations for each observation' \
                                     ' are reported in the latitude, longitude, and altitude variables..',
            'site_utc2lst': TZ,
            'site_utc2lst_comment': 'Add site_utc2lst hours to convert a time stamp in UTC (Coordinated ' \
                                    'Universal Time) to LST (Local Standard Time).',
            'site_url': station.org.self.uri,
            'site_oscar_id': oscarId,
            'warning_dataset_scale': warning,
            'dataset_creation_date': dt.datetime.now().isoformat(),
            'dataset_num': nc_cnt,
            'dataset_name': f_name,
            'dataset_globalview_prefix': station.id + '_' + str(lab_id) + 'C0',
            'dataset_process': "PassThru",
            'dataset_alternative_names': 'NA',
            'dataset_alternative_names_description': 'The attribute dataset_alternative_names is used to identify ' \
                                                     'all other dataset names that have been used for the record in this dataset. To obtain the full ' \
                                                     'record for this dataset please use all alternatively named datasets that appear in this ObsPack ' \
                                                     'product and the corresponding release of other ObsPacks if applicable.',
            'dataset_alternative_names_comment': '',
            'dataset_parameter': c.gas,
            'dataset_project': 'surface-insitu or tower-insitu',
            'dataset_platform': 'fixed',
            'dataset_map': 'https://meta.icos-cp.eu/station/?station=/resources/stations/AS_' + station.id + '&icon=https://static.icos-cp.eu/share/stations/icons/as.png',
            'dataset_selection': 'all hourly data from ' + str(
                hgh) + ' magl intake',
            'dataset_selection_tag': 'allvalid-' + str(hgh) + 'magl',
            'dataset_comment': 'Please note that some datasets included in past Obspack releases are now ' \
                               'provided by the ICOS program. The valid data selection scheme for ICOS datasets may differ ' \
                               'significantly from the selection scheme provided previously by contributing laboratories.)',
            'dataset_contains_ICOS_L1_and_or_L2_data': isICOS,
            'dataset_calibration_scale': calib_scale,
            'dataset_start_date': timeseries_start,
            'dataset_stop_date': timeseries_end,
            'dataset_data_frequency': 1.,
            'dataset_data_frequency_unit': 'hour',
            'dataset_time_window_lst': '0-23',
            'dataset_time_window_utc': '0-23',
            'dataset_time_window_exclusion': 'F',
            'dataset_intake_ht': str(hgh),
            'dataset_intake_ht_unit': 'magl',
            'dataset_description': 'This data package is intended for use in carbon cycle inverse modeling, model ' \
                                   'evaluation, and satellite validation studies.  Please report errors and send comments regarding ' \
                                   'this product to the ObsPack originators. Please read carefully the ObsPack Fair Use statement ' \
                                   'and cite appropriately. DOI metadata for this product are available ' \
                                   'at https://search.datacite.org/works/10.18160/' + doi_cite + '.',
            'dataset_usage_url': 'https://doi.org/10.18160/' + doi_cite,
            'dataset_usage_description': 'In addition to this product\'s citation we ask that you please cite ' \
                                         'the following provider citations when using data from this dataset.',
            'dataset_provider_citation_total': str(len(citations))}

    for i in range(0, len(citations)):
        attr.update({'dataset_provider_citation_' + str(i + 1): citations[i]})

    attr2 = {
        'dataset_provider_license': 'DATA POLICY: ICOS DATA is licensed under a Creative Commons Attribution ' \
                                    '4.0 international licence (http://creativecommons.org/licenses/by/4.0/.The ICOS data licence is ' \
                                    'described at https://data.icos-cp.eu/licence.',
        'dataset_provider_license_url': 'http://creativecommons.org/licenses/by/4.0/',
        'dataset_reference_total_listed': 0,
        'dataset_contribution': 'These data are provided by ICOS-RI AND ' + lab_name + ' AND ICOS ATC, CAL, Carbon Portal. ' \
                                                                                      'Principal investigators and contributors include ' + persons + '.',
        'obspack_variables_and_attributes': 'ObsPack variables and attributes are described at ' \
                                            'www.gml.noaa.gov/ccgg/obspack/documentation.html#MetaData',
        'obspack_name': obspack_name,
        'obspack_description': 'This data file is part of a data package called Obspack that is intended ' \
                               'for use in carbon cycle inverse modeling, model ' \
                               'evaluation, and satellite validation studies.  Please report errors and send comments regarding this ' \
                               'product to the ObsPack originators. Please read carefully the ObsPack Fair Use statement and cite ' \
                               'appropriately. DOI metadata for this product are available at ' \
                               'https://search.datacite.org/works/10.18160/' + doi_cite + \
                               'Please visit http://www.gml.noaa.gov/ccgg/obspack/ for more information.',
        'obspack_creation_date': dt.datetime.now().isoformat(),
        'obspack_warning': 'Every effort is made to create the most accurate and precise data product possible.' \
                           ' Contributors reserve the right to make corrections to this product and data based on recalibration of ' \
                           'standard gases or for other reasons deemed scientifically justified. Contributors to this product are ' \
                           'not responsible for results and conclusions based on use of this product without regard to this warning.',
        'obspack_fair_use': 'This cooperative data product is made freely available to the scientific community ' \
                            'and is intended to stimulate and support carbon cycle modeling studies.  We rely on the ethics and ' \
                            'integrity of the user to assure that each contributing national and university laboratory receives ' \
                            'fair credit for their work. Fair credit will depend on the nature of the work and the requirements of ' \
                            'the institutions involved.Your use of this data product implies an agreement to contact each ' \
                            'contributing laboratory for data sets used to discuss the nature of the work and the appropriate level' \
                            'of acknowledgement. If this product is essential to the work, or if an important result or conclusion ' \
                            'depends on this product, co-authorship may be appropriate. This should be discussed with the ' \
                            'appropriate data providers at an early stage in the work.  Contacting the data providers is not ' \
                            'optional; if you use this data product, you must contact the applicable data providers. To help you ' \
                            'meet your obligation, the data product includes an e-mail distribution list of all data providers. ' \
                            'This data product must be obtained directly from the ICOS Data Portal at ' \
                            'https://data.icos-cp.eu/portal/ and we ask you to not re-distribute. In addition to the conditions of ' \
                            'fair use as stated above, users are requested to include the ObsPack product citation in any publication or ' \
                            'presentation using the product.  The required citation is included in every data product.',
        'obspack_usage_policy': 'https://www.icos-cp.eu/data-services/about-data-portal/data-license',
        'obspack_data_license': 'https://creativecommons.org/licenses/by/4.0/',
        'obspack_identifier_link': settings['doi_collection'],
        'obspack_citation': doi_citation('https://doi.org/10.18160/' + doi_cite),
        'Conventions': 'CF-1.7',
        'nc.institution': 'Unidata',
        'source': 'ICOS RI',
        'history': str(
            dt.datetime.utcnow()) + ' Python in Jupyter notebook createObspackv34.ipynb'
    }
    attr.update(attr2)
    ds.setncatts(attr)

    #    except:
    #        print('Error in writing netcdf ',f_name)
    #        ds.close()
    #        raise
    #    finally:
    ds.sync()
    ds.close()

    if c.do_txt:
        csv_data = pd.DataFrame()
        csv_data['datetimeISO'] = isof
        csv_data['year'] = [dt.datetime.utcfromtimestamp(i).year for i in tim]
        csv_data['month'] = [dt.datetime.utcfromtimestamp(i).month for i in tim]
        csv_data['day'] = [dt.datetime.utcfromtimestamp(i).day for i in tim]
        csv_data['hour'] = [dt.datetime.utcfromtimestamp(i).hour for i in tim]
        csv_data['minute'] = [dt.datetime.utcfromtimestamp(i).minute for i in tim]
        csv_data['second'] = [dt.datetime.utcfromtimestamp(i).second for i in tim]
        csv_data['time'] = tim
        csv_data['time_decimal'] = timdec
        csv_data['value'] = scaleAndMask(df, 'Meas', 1 / factor).values
        csv_data['value_std_dev'] = scaleAndMask(df, 'Stdev', 1 / factor).values
        csv_data['nvalue'] = df.NbPoints.values
        csv_data['qc_flag'] = df.Flag.values
        csv_data['icos_datalevel'] = df.Level.values
        try:
            csv_data['icos_LTR'] = scaleAndMask(df, 'LTR', 1 / factor).values
            csv_data['icos_CMR'] = scaleAndMask(df, 'CMR', 1 / factor).values
            csv_data['icos_STTB'] = scaleAndMask(df, 'STTB', 1 / factor).values
        except (
                KeyError, AttributeError, TypeError, ValueError, ZeroDivisionError, NameError
        ) as column_exception:
            csv_data['icos_LTR'] = np.nan
            csv_data['icos_CMR'] = np.nan
            csv_data['icos_STTB'] = np.nan
        csv_data['latitude'] = station.location.lat
        csv_data['longitude'] = station.location.lon
        csv_data['altitude'] = float(station.location.alt) + hgh
        csv_data['intake_height'] = hgh
        csv_data['unique_sample_location_num'] = np.arange(1, len(df) + 1, 1)
        csv_data['obspack_num'] = np.arange(cntAll + 1, cntAll + len(df) + 1, 1)
        csv_data['obspack_id'] = [
            obspack_name + '~' + f_name + '~' + str(cntAll + i + 1) for i in
            range(len(df))]

        csv_path = Path(c.txt, f'{f_name}.txt')
        csv_data.to_csv(csv_path, sep=' ', na_rep='-999999', header=True, index=False, float_format='%.5f')
        header = create_txt_header(obs_name=obspack_name, nc_file=nc_name, doi_cite=doi_cite)

        with open(csv_path, 'r') as file_handle:
            csv = file_handle.readlines()
        with open(csv_path, 'w') as file_handle:
            for i in header:
                file_handle.write(i + '\n')
            for i in csv:
                file_handle.write(i)
        # print('Done saving ', csv_path)

    cntAll = cntAll + len(df)

    spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackTimeSerieResult'
    if c.gas == 'ch4':
        spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackCH4TimeSeriesResult'
    if c.gas == 'n2o':
        spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackN2oTimeSeriesResult'

    res = generate_meta(f_name=nc_name, obj_spec=spec_url, input_doi=f'10.18160/{doi_cite}', scale=calib_scale)
    pretty = json.dumps(res, indent=2)
    json_f_name = Path(c.json, f'{nc_name.stem}.json')
    with open(json_f_name, 'w') as f:
        f.write(pretty)
    # print('Done saving ', json_f_name)


def generate_meta(
        f_name: Path = None,
        obj_spec: str = None,
        input_doi: str = None,
        scale: str = None
) -> dict[str, Any]:
    """Generate and upload metadata."""
    f_name_str = str(f_name.resolve())
    xarray_ds = xr.open_dataset(f_name)
    try:
        variable = [variable for variable in ['co2_', 'ch4_', 'co_', 'n2o_'] if variable in f_name_str]
        if len(variable) != 1:
            exit(f'\tError! Incorrect number of variables detected: {variable} file: {f_name_str}.\n'
                 f'\tNeed to have only one variable specified in file\'s name.\n'
                 f'\tExiting...')
        variable = variable[0][0:-1]

        json_package = {
            "submitterId": "CP",
            "hashSum": get_hash_sum(path=f_name),
            "fileName": f_name.name,
            "specificInfo": {
                "station": xarray_ds.site_url,
                "samplingHeight": xarray_ds.intake_height[0].item(),
                "production": {
                    "creator": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "contributors": c.file_contribs.uri.to_list(),
                    "hostOrganization": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "comment": "European Obspack observational timeseries in netcdf format of ambient mole "
                               f"fraction of {variable} in dry air calibrated using the WMO GAW calibration "
                               f"scale {scale}, composed of (all whenever available) historical PI QCed "
                               f"data, ICOS Level 2 data and ICOS NRT data",
                    "creationDate": xarray_ds.dataset_creation_date+"Z",
                    "sources": c.d_files
                }
            },
            "objectSpecification": obj_spec,
            "isNextVersionOf": [get_prev_by_name(anchor=f_name.name)],
            "preExistingDoi": input_doi.replace('https://doi.org/', ''),
            "references": {
                "autodeprecateSameFilenameObjects": True,
                "keywords": [scale, "atmospheric dry air "+variable+" mole fraction"]
            }
        }
    finally:
        xarray_ds.close()
    return json_package


# Main program for producing obspack nc files from icos and non-icos
# timeseries of atmosphere data.
useflags = True
printas = '.png'  # set to None for no saving of plots

c = Config().c
init()
info = process_obspack()
run_all(meta_info=info, process=True)

