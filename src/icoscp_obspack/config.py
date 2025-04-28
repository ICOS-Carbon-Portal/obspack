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
    lab_numbers: [str | pd.DataFrame]
    icos_stations: [str | pd.DataFrame]
    cache: Optional[str] = None
    file_contribs: Optional[pd.DataFrame] = None
    col_contribs: Optional[pd.DataFrame] = None
    mauna_loa: Optional[str] = None
    ml: Optional[str] = None
    glb_avg_ch4: Optional[str] = None
    debug: bool = True
    debug_info: Optional[str | pd.DataFrame] = 'input/debug/info.csv'


class Config:

    def __init__(self) -> None:
        self.config = self.read_config()
        self.config.output = self.config.output if self.config.output else 'output'
        self.config.mauna_loa = f'{self.config.output}/mauna_loa.csv'
        self.config.ml = f'{self.config.output}/ml.csv'
        self.config.glb_avg_ch4 = f'{self.config.output}/glb_avg_ch4.csv'
        self.config.lab_numbers = pd.read_csv(self.config.lab_numbers,
                                              comment='#', delimiter=';')
        self.config.icos_stations = pd.read_csv(self.config.icos_stations,
                                                comment='#', delimiter=';')
        self.config.cache = Path(self.config.output, 'cache')
        self.file_contribs = pd.DataFrame()
        self.col_contributors = pd.DataFrame()
        if self.config.debug:
            print('DEBUG MODE ON')
            print('-------------')
            self.config.debug_info = pd.read_csv(self.config.debug_info)
        self.init_files()
        return

    @staticmethod
    def read_config() -> YamlConfig:
        with open(file=y.YAML_CONFIG, mode='r') as yaml_handler:
            return YamlConfig(**yaml.safe_load(yaml_handler))

    def init_files(self) -> None:
        """Create the needed application directories."""
        Path(self.config.output).mkdir(parents=True, exist_ok=True)
        Path(self.config.cache).mkdir(parents=True, exist_ok=True)
