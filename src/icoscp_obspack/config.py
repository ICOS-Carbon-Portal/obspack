# Standard library imports.
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError

# Related third party imports.
import pandas as pd
import yaml

# Local application/library specific imports.
from icoscp_obspack.constants import yaml as y
from icoscp_obspack.utils import t2dt


@dataclass()
class YamlConfig:
    gas: str
    analyse: bool
    plot: bool
    output: str
    nc: str
    json: str
    txt: str
    png: str
    pickle: str | None
    zip: str | None
    lab_numbers: str | pd.DataFrame = 'input/lab_numbers.csv'
    icos_stations: str | pd.DataFrame = 'input/icos_stations.csv'
    header: str = 'input/header.txt'
    glob_aver: pd.DataFrame = None
    file_contribs: pd.DataFrame = field(default_factory=pd.DataFrame)
    col_contribs: pd.DataFrame = field(default_factory=pd.DataFrame)
    d_files: list = None
    mauna_loa: str | None = None
    ml: str | None = None
    glb_avg_ch4: str | None = None
    do_png: bool = True
    do_txt: bool = True
    debug: bool = True
    meta_info: pd.DataFrame = field(default_factory=pd.DataFrame)
    refresh_pickles: bool = False
    produced: pd.DataFrame = field(default_factory=pd.DataFrame)


class Config:

    def __init__(self) -> None:
        self.c = self.read_config()
        self.c.output = self.c.output if self.c.output else Path('output', self.c.gas)
        self.c.nc = self.c.nc if self.c.nc else Path(self.c.output, 'nc-files')
        self.c.json = self.c.json if self.c.json else Path(self.c.output, 'json-files')
        self.c.txt = self.c.txt if self.c.txt else Path(self.c.output, 'txt-files')
        self.c.png = self.c.png if self.c.png else Path(self.c.output, 'png-files')
        self.c.pickle = self.c.pickle if self.c.pickle else Path(self.c.output, 'pickle-files')
        self.c.zip = self.c.zip if self.c.zip else Path(self.c.output, 'zip-files')
        self.init_dirs()
        self.c.mauna_loa = Path(self.c.output, 'mauna_loa.csv')
        self.c.ml = Path(self.c.output, 'ml.csv')
        self.c.glb_avg_ch4 = Path(self.c.output, 'glb_avg_ch4.csv')
        self.c.lab_numbers = pd.read_csv(self.c.lab_numbers, comment='#', delimiter=';')
        self.c.icos_stations = pd.read_csv(self.c.icos_stations, comment='#', delimiter=';')
        self.c.glob_aver = self.get_global_average()
        if self.c.debug:
            print(f'Running obspack for gas: "{self.c.gas}" in debug mode...')
            print('-------------')

    @staticmethod
    def read_config() -> YamlConfig:
        with open(y.YAML_CONFIG) as yaml_handler:
            return YamlConfig(**yaml.safe_load(yaml_handler))

    def init_dirs(self) -> None:
        """Create the needed application directories."""
        Path(self.c.output).mkdir(parents=True, exist_ok=True)
        Path(self.c.nc).mkdir(parents=True, exist_ok=True)
        Path(self.c.json).mkdir(parents=True, exist_ok=True)
        Path(self.c.txt).mkdir(parents=True, exist_ok=True)
        Path(self.c.png).mkdir(parents=True, exist_ok=True)
        Path(self.c.pickle).mkdir(parents=True, exist_ok=True)
        Path(self.c.zip).mkdir(parents=True, exist_ok=True)

    def get_global_average(self) -> pd.DataFrame:
        skip_rows = 58 if self.c.gas == 'co2' else 65
        url = f'https://gml.noaa.gov/webdata/ccgg/trends/{self.c.gas}/{self.c.gas}_mm_gl.txt'
        global_aver_path = Path(self.c.output, f'{self.c.gas}_mm_gl.txt')
        try:
            global_aver = pd.read_csv(url, skiprows=skip_rows, header=None,
                                      names=['JulDate', 'Meas', 'Trend'],
                                      delimiter=r'\s+', usecols=[2, 3, 5])
        except (HTTPError, URLError) as e:
            print(f'HTTP or URL error occurred: {e}')
            print(f'Trying cache in "{global_aver_path}"')
            global_aver = pd.read_csv(global_aver_path)
        except Exception as e:
            print(f'Unexpected error: {e}')
            raise e
        else:
            global_aver = global_aver.query('Meas>20')
            global_aver['DateTime'] = [t2dt(i) for i in global_aver.JulDate]
            global_aver.set_index('DateTime', inplace=True)
            global_aver.to_csv(f'{self.c.output}/{self.c.gas}_mm_gl.txt')
        return global_aver
