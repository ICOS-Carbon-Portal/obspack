# Standard library imports.
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
# Related third party imports.
import pandas as pd
import yaml
# Local application/library specific imports.
from icoscp_obspack.constants import yaml as y


@dataclass()
class YamlConfig:
    gas: str
    analyse: bool
    plot: bool
    output: str
    data: str
    nc: str
    png: str
    txt: str
    lab_numbers: [str | pd.DataFrame]
    icos_stations: [str | pd.DataFrame]
    cache: Optional[str] = None
    file_contribs: pd.DataFrame = None
    col_contribs: pd.DataFrame = None
    mauna_loa: Optional[str] = None
    ml: Optional[str] = None
    glb_avg_ch4: Optional[str] = None
    do_txt: bool = True
    debug: bool = True
    debug_info: Optional[str | pd.DataFrame] = 'input/debug/info.csv'


class Config:

    def __init__(self) -> None:
        self.c = self.read_config()
        self.c.output = self.c.output if self.c.output else 'output'
        self.c.data = self.c.data if self.c.data else Path(self.c.output, 'data')
        self.c.nc = self.c.nc if self.c.nc else Path(self.c.data, self.c.gas, 'nc-files')
        self.c.png = self.c.png if self.c.png else Path(self.c.data, self.c.gas, 'png-files')
        self.c.txt = self.c.txt if self.c.txt else Path(self.c.data, self.c.gas, 'txt-files')
        self.c.mauna_loa = Path(self.c.output, 'mauna_loa.csv')
        self.c.ml = Path(self.c.output, 'ml.csv')
        self.c.glb_avg_ch4 = Path(self.c.output, 'glb_avg_ch4.csv')
        self.c.lab_numbers = pd.read_csv(self.c.lab_numbers, comment='#', delimiter=';')
        self.c.icos_stations = pd.read_csv(self.c.icos_stations, comment='#', delimiter=';')
        self.c.cache = Path(self.c.output, self.c.gas, 'cache')
        self.c.file_contribs = pd.DataFrame()
        self.c.col_contribs = pd.DataFrame()
        if self.c.debug:
            print('DEBUG MODE ON')
            print('-------------')
            self.c.debug_info = pd.read_csv(self.c.debug_info)
        self.init_files()
        return

    @staticmethod
    def read_config() -> YamlConfig:
        with open(file=y.YAML_CONFIG, mode='r') as yaml_handler:
            return YamlConfig(**yaml.safe_load(yaml_handler))

    def init_files(self) -> None:
        """Create the needed application directories."""
        Path(self.c.output).mkdir(parents=True, exist_ok=True)
        Path(self.c.data).mkdir(parents=True, exist_ok=True)
        Path(self.c.cache).mkdir(parents=True, exist_ok=True)

