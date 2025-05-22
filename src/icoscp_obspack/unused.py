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
