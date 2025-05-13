# Standard library imports.
from pathlib import Path

# Related third party imports.
import pandas as pd
import requests

# Local application/library specific imports.
from icoscp_obspack.utils import get_cookie_jar
from icoscp_obspack.constants import icons


gas = input('Please specify gas ("co2", "ch4", "n2o"): ')
produced = pd.read_csv(f'output/{gas}/produced.csv')
collection = []
for i, row in produced.iterrows():
    data_file_path = Path(row.folder, f'{row.fname}.nc')
    json_file_path = Path(row.folder.replace('nc-files', 'json-files'), f'{row.fname}.json')
    # Upload metadata.
    upload_meta_resp = requests.post(
        url='https://meta.icos-cp.eu/upload',
        data=open(file=json_file_path, mode='rb'),
        headers={'content-type': 'application/json', 'Accept-Charset': 'UTF-8'},
        cookies=get_cookie_jar()
    )
    landing_page = upload_meta_resp.text.replace('data', 'meta')
    collection.append(landing_page)
    # Upload data.
    upload_data_resp = requests.put(
        url=upload_meta_resp.text,
        cookies=get_cookie_jar(),
        headers={'Content-Type': 'application/octet-stream'},
        data=open(file=data_file_path, mode='rb')
    )
    if upload_data_resp.status_code == 200:
        print(landing_page, icons.ICON_CHECK)
with open(f'output/{gas}/{gas}_collection.txt', 'w') as f_handle:
    for item in collection:
        f_handle.write(f'{item}\n')
