# Standard library imports.
import sys
from http import HTTPStatus
from http.cookiejar import CookieJar
from pathlib import Path

# Related third party imports.
import pandas as pd
import requests
from icoscp_core.icos import auth

# Local application/library specific imports.
from icoscp_obspack.config import Config


def main():
    config = Config()
    produced = pd.read_csv(config.info_about_produced_files)
    cookies = get_cookie_jar()
    collection: list[str] = []
    for _, row in produced.iterrows():
        json_file_path = Path(config.json, f"{row['filename']}.json")
        data_file_path = Path(config.nc, f"{row['filename']}.nc")
        print(json_file_path)
        # Upload metadata.
        upload_meta_resp = requests.post(
            url='https://meta.icos-cp.eu/upload',
            data=open(file=json_file_path, mode='rb'),
            headers={'Content-Type': 'application/json', 'Accept-Charset': 'UTF-8'},
            cookies=cookies
        )
        if upload_meta_resp.status_code == HTTPStatus.OK:
            landing_page = upload_meta_resp.text.replace('data', 'meta')
            collection.append(landing_page)
        else:
            # Todo: correctly try-except the http request.
            print(upload_meta_resp.text)
            sys.exit('Something went wrong when uploading metadata. The application will now exit.')
        # Upload data.
        upload_data_resp = requests.put(
            url=upload_meta_resp.text,
            cookies=cookies,
            headers={'Content-Type': 'application/octet-stream'},
            data=open(file=data_file_path, mode='rb')
        )
        if upload_data_resp.status_code == HTTPStatus.OK:
            print(landing_page, '\u2713')
        else:
            # Todo: correctly try-except the http request.
            print(upload_data_resp.text)
            sys.exit('Something went wrong when uploading data. The application will now exit.')
    with open(f'output/{config.gas}_collection.txt', 'w') as f_handle:
        for item in collection:
            f_handle.write(f'{item}\n')


def get_cookie_jar() -> CookieJar | None:
    cookie_string = ''
    cookie_jar: CookieJar | None = None
    cookie_dict: dict[str, str] = {}
    try:
        cookie_string = auth.get_token().cookie_value
    except Exception as e:
        if "Config file does not exist" in str(e):
            auth.init_config_file()
            cookie_string = auth.get_token().cookie_value
        elif "Incorrect user name or password" in str(e):
            auth.init_config_file()
            cookie_string = auth.get_token().cookie_value
        else:
            print("Got a weird exception...", e)
    else:
        # Convert string to dictionary.
        cookie_dict: dict[str, str] = {
            cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookie_string.split("; ")}
    finally:
        if cookie_string:
            # Convert dictionary to RequestsCookieJar.
            cookie_jar = requests.utils.cookiejar_from_dict(cookie_dict)
    return cookie_jar


if __name__ == '__main__':
    main()
