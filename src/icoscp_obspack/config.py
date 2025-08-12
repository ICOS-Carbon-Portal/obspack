# Standard library imports.
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

# Related third party imports.
import yaml

# Local application/library specific imports.
from icoscp_obspack.citation import doi_citation

YAML_CONFIG = '../config.yml'


@dataclass()
class YamlConfig:
    gas: str
    doi: str
    dois_for_default_citations: list[str]
    obspack_product_name: str
    obspack_product_version: str
    input: Optional[str]
    output: Optional[str]
    nc: Optional[str]
    json: Optional[str]
    txt: Optional[str]
    png: Optional[str]
    pickle: Optional[str]
    zip: Optional[str]
    use_cached_datafiles: Optional[bool]
    analyse: Optional[bool]
    do_png: Optional[bool]
    display_plots: Optional[bool]
    do_txt: Optional[bool]
    debug: Optional[bool]
    refresh_pickles: Optional[bool]
    use_mauna_loa_for_global_co2: Optional[bool]
    use_flags: Optional[bool]
    lab_numbers: Optional[str]
    icos_stations: Optional[str]
    header: Optional[str]
    default_contributor_weight: Optional[int]
    print_timing_messages: Optional[bool]


class Config:

    def __init__(self) -> None:
        with open(YAML_CONFIG) as yaml_handler:
            config = YamlConfig(**yaml.safe_load(yaml_handler))

        if config.gas not in ['co2', 'ch4', 'n2o', 'co']:
            raise ValueError(f"Invalid gas: {config.gas}.\nPossible values are 'co2', 'ch4', 'n2o', 'co'.")

        if config.debug:
            print(f'Running obspack for gas: "{config.gas}" in debug mode...')
        else:
            print(f'Running obspack for gas: "{config.gas}" in normal mode...')
        print('-------------')

        self.gas: str = config.gas
        self.doi: str = config.doi
        self.citation: str = doi_citation(config.doi)
        self.default_citations: list[str] = [doi_citation(doi) for doi in config.dois_for_default_citations]
        self.obspack_product_name: str = config.obspack_product_name
        self.obspack_product_version: str = config.obspack_product_version

        self.use_cached_datafiles: bool = config.use_cached_datafiles or False
        self.analyse: bool = config.analyse or True
        self.do_png: bool = config.do_png or True
        self.display_plots: bool = config.display_plots or False
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
        self.file_lab_numbers: Path = self._init_path(
            Path(self.input, 'lab_numbers.csv'), config.lab_numbers, 'file')
        self.file_icos_stations: Path = self._init_path(
            Path(self.input, 'icos_stations.csv'), config.icos_stations, 'file')

        self.conversion_factor: float
        self.calibration_scale: str
        if config.gas == 'co2':
            self.conversion_factor = 1e-6
            self.calibration_scale = 'WMO CO2 X2019'
            self.plot_gas_label = 'CO${_2}$'
            self.plot_unit_label = '[µmol/mol]'
            self.plot_limy = [380, 460]
        elif config.gas == 'ch4':
            self.conversion_factor = 1e-9
            self.calibration_scale = 'WMO X2004A'
            self.plot_gas_label = 'CH${_4}$'
            self.plot_unit_label = '[nmol/mol]'
            self.plot_limy = [1800, 2500]
        elif config.gas == 'n2o':
            self.conversion_factor = 1e-9
            self.calibration_scale = 'NOAA-2006A'
            self.plot_gas_label = 'N${_2}$O'
            self.plot_unit_label = '[nmol/mol]'
            self.plot_limy = [315, 370]
        elif config.gas == 'co':
            self.conversion_factor = 1e-9
            self.calibration_scale = 'WMO X2014A'
            self.plot_gas_label = 'CO'
            self.plot_unit_label = '[nmol/mol]'
            self.plot_limy = [0, 600]

        self.default_contributor_weight: int = config.default_contributor_weight or 0
        self.print_timing_messages: bool = config.print_timing_messages or False


    def _init_path(
            self, default_path: Path, user_specified_path: Optional[str],
            path_type: Optional[Literal["dir", "file"]] = "dir") -> Path:
        """Initialize the path to a newly produced file or an application directory
        to store newly produced files."""
        path = default_path if user_specified_path is None else Path(user_specified_path)
        if path_type == "dir" and not path.exists():
            path.mkdir(parents=True)
            print(f"Created directory '{path}'")
        return path
