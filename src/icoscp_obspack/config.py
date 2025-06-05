# Standard library imports.
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from urllib.error import HTTPError, URLError

# Related third party imports.
import pandas as pd
import yaml

# Local application/library specific imports.
from icoscp_obspack.utils.ts_filter import ghg_filter_ts
from icoscp_obspack.utils.utils import t2dt

YAML_CONFIG = '../config.yml'


@dataclass()
class YamlConfig:
    gas: str
    doi: str
    submitted_after: str
    input: Optional[str]
    output: Optional[str]
    nc: Optional[str]
    json: Optional[str]
    txt: Optional[str]
    png: Optional[str]
    pickle: Optional[str]
    zip: Optional[str]
    analyse: Optional[bool]
    plot: Optional[bool]
    do_png: Optional[bool]
    do_txt: Optional[bool]
    debug: Optional[bool]
    refresh_pickles: Optional[bool]
    use_mauna_loa_for_global_co2: Optional[bool]
    use_flags: Optional[bool]
    lab_numbers: Optional[str]
    icos_stations: Optional[str]
    header: Optional[str]


class Config:

    def __init__(self) -> None:
        with open(YAML_CONFIG) as yaml_handler:
            config = YamlConfig(**yaml.safe_load(yaml_handler))

        if config.debug:
            print(f'Running obspack for gas: "{config.gas}" in debug mode...')
            print('-------------')

        self.gas: str = config.gas
        self.submitted_after: datetime = datetime.fromisoformat(config.submitted_after)

        self.analyse: bool = config.analyse or True
        self.plot: bool = config.plot or False
        self.do_png: bool = config.do_png or True
        self.do_txt: bool = config.do_txt or True
        self.debug: bool = config.debug or False
        self.refresh_pickles: bool = config.refresh_pickles or False
        self.use_mauna_loa_for_global_co2: bool = config.use_mauna_loa_for_global_co2 or False
        self.useflags: bool = config.use_flags or True

        self.input: Path = self._init_path(Path('input'), config.input)
        self.output: Path = self._init_path(Path('output', config.gas), config.output)
        self.nc: Path = self._init_path(Path(self.output, 'nc-files'), config.nc)
        self.json: Path = self._init_path(Path(self.output, 'json-files'), config.json)
        self.txt: Path = self._init_path(Path(self.output, 'txt-files'), config.txt)
        self.png: Path = self._init_path(Path(self.output, 'png-files'), config.png)
        self.pickle: Path = self._init_path(Path(self.output, 'pickle-files'), config.pickle)
        self.zip: Path = self._init_path(Path(self.output, 'zip-files'), config.zip)
        self.header: Path = self._init_path(Path(self.input, 'header.txt'), config.header, 'file')

        file_lab_numbers: Path = self._init_path(Path(self.input, 'lab_numbers.csv'), config.lab_numbers, 'file')
        file_icos_stations: Path = self._init_path(Path(self.input, 'icos_stations.csv'), config.icos_stations, 'file')
        self.lab_numbers: pd.DataFrame = pd.read_csv(file_lab_numbers, comment='#', delimiter=';')
        self.icos_stations: pd.DataFrame = pd.read_csv(file_icos_stations, comment='#', delimiter=';')

        self.global_avg: pd.DataFrame = self._get_global_average()
        self.global_avg_filtered: pd.DataFrame = ghg_filter_ts(self.global_avg.JulDate, self.global_avg.Meas) if self.analyse else pd.DataFrame()

        self.cntAll: int = 0
        self.d_files: list = []
        self.produced = pd.DataFrame()
        self.file_contribs = pd.DataFrame()
        self.col_contribs = pd.DataFrame()


    def _init_path(
            self, default_path: Path, user_specified_path: Optional[str],
            path_type: Optional[Literal["dir", "file"]] = "dir") -> Path:
        """Initialize the path to a newly produced file or an application directory
        to store newly produced files."""
        path = default_path if user_specified_path is None else Path(user_specified_path)
        if path_type == "dir":
            path.mkdir(parents=True, exist_ok=True)
        return path


    def _get_global_average(self) -> pd.DataFrame:
        if self.gas == 'co2' and self.use_mauna_loa_for_global_co2:
            # Get the most recent Mauna Loa CO2 data.
            url = 'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_weekly_mlo.txt'
            skip_rows = 37
            names = ['JulDate', 'Meas']
            cols = [3, 4]
            global_avg_path = Path(self.output, 'co2_weekly_mlo.txt')
        else:
            # Get the most recent monthly marine BL global averages.
            url = f'https://gml.noaa.gov/webdata/ccgg/trends/{self.gas}/{self.gas}_mm_gl.txt'
            skip_rows = 58 if self.gas == 'co2' else 65
            names = ['JulDate', 'Meas', 'Trend']
            cols = [2, 3, 5]
            global_avg_path = Path(self.output, f'{self.gas}_mm_gl.txt')
        try:
            global_avg = pd.read_csv(
                url, skiprows=skip_rows, header=None,
                names=names, delimiter=r'\s+', usecols=cols)
        except (HTTPError, URLError) as e:
            print(f'HTTP or URL error occurred: {e}')
            print(f'Trying cache in "{global_avg_path}"')
            global_avg = pd.read_csv(global_avg_path)
        except Exception as e:
            print(f'Unexpected error: {e}')
            raise e
        else:
            global_avg = global_avg.query('Meas>20')
            global_avg['DateTime'] = global_avg['JulDate'].apply(t2dt)
            global_avg.set_index('DateTime', inplace=True)
            global_avg.to_csv(global_avg_path)
        return global_avg
