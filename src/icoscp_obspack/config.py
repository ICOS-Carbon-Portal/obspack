# Standard library imports.
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Related third party imports.
import yaml

# Local application/library specific imports.
from icoscp_obspack.citation import doi_citation

YAML_CONFIG = '../config.yml'


@dataclass()
class YamlConfig:
    gas: str
    doi: str
    all_gases_obspack_doi: str
    dois_for_default_citations: list[str]
    obspack_product_description: str
    obspack_product_name: str | None
    obspack_product_version: str | None
    major_version_for_doi: int
    minor_version_for_doi: int
    title_for_doi: str
    description_for_doi: str
    subjects_for_doi: list[str]
    publisher_for_doi: str | None
    resource_type_for_doi: str | None
    format_info_for_doi: str | None
    rights_for_doi: str | None
    rights_uri_for_doi: str | None
    input: str | None
    output: str | None
    doi_json_file: str | None
    info_about_produced_files: str | None
    nc: str | None
    json: str | None
    txt: str | None
    png: str | None
    pickle: str | None
    zip: str | None
    use_only_icos_stations_l1_or_l2: bool | None
    use_cached_datafiles: bool | None
    analyse: bool | None
    do_png: bool | None
    display_plots: bool | None
    do_txt: bool | None
    debug: bool | None
    refresh_pickles: bool | None
    use_mauna_loa_for_global_co2: bool | None
    use_flags: bool | None
    lab_numbers: str | None
    icos_stations: str | None
    header: str | None
    default_author_weight: int | None
    print_timing_messages: bool | None


class Config:
    def __init__(self) -> None:
        with open(YAML_CONFIG) as yaml_handler:
            config = YamlConfig(**yaml.safe_load(yaml_handler))

        self.gas: str = config.gas
        self.doi: str = config.doi
        self.all_gases_obspack_doi: str = config.all_gases_obspack_doi
        self.default_citations: list[str] = [doi_citation(doi) for doi in config.dois_for_default_citations]
        self.obspack_product_description: str = config.obspack_product_description
        self.obspack_product_name: str | None = config.obspack_product_name
        self.obspack_product_version: str = self._value_with_default(
            config.obspack_product_version,
            f'v{config.major_version_for_doi}.{config.minor_version_for_doi}')
        self.major_version_for_doi: int = config.major_version_for_doi
        self.minor_version_for_doi: int = config.minor_version_for_doi
        self.title_for_doi: str = config.title_for_doi
        self.description_for_doi: str = config.description_for_doi
        self.subjects_for_doi: list[str] = config.subjects_for_doi
        self.publisher_for_doi: str = self._value_with_default(
            config.publisher_for_doi, 'ICOS ERIC - Carbon Portal')
        self.resource_type_for_doi: str = self._value_with_default(
            config.resource_type_for_doi, 'compressed ZIP archive')
        self.format_info_for_doi: str = self._value_with_default(
            config.format_info_for_doi, (
                'Compressed ZIP archive of netcdf and ASCII files with semicolon separated columns.'
                ' Overview pictures of recent data and trend plots since 2010 are provided as bitmaps'
                ' in png format.')
            )
        self.rights_for_doi: str = self._value_with_default(
            config.rights_for_doi, 'Creative Commons Attribution 4.0 International')
        self.rights_uri_for_doi: str = self._value_with_default(
            config.rights_uri_for_doi, 'https://creativecommons.org/licenses/by/4.0/legalcode')

        self.use_only_icos_stations_l1_or_l2: bool = self._value_with_default(
            config.use_only_icos_stations_l1_or_l2, True)
        self.use_cached_datafiles: bool = self._value_with_default(config.use_cached_datafiles, False)
        self.analyse: bool = self._value_with_default(config.analyse, True)
        self.do_png: bool = self._value_with_default(config.do_png, True)
        self.display_plots: bool = self._value_with_default(config.display_plots, False)
        self.do_txt: bool = self._value_with_default(config.do_txt, True)
        self.debug: bool = self._value_with_default(config.debug, False)
        self.refresh_pickles: bool = self._value_with_default(config.refresh_pickles, False)
        self.use_mauna_loa_for_global_co2: bool = self._value_with_default(
            config.use_mauna_loa_for_global_co2, False)
        self.useflags: bool = self._value_with_default(config.use_flags, True)

        self.input: Path = self._init_path(Path('input'), config.input)
        self.output: Path = self._init_path(Path('output', config.gas), config.output)
        self.doi_json_file: Path = self._init_path(
            Path(self.output, f'doi_json_{config.gas}.json'), config.doi_json_file, 'file')
        self.info_about_produced_files: Path = self._init_path(
            Path(self.output, f'info_about_produced_files_for_{config.gas}.csv'),
            config.info_about_produced_files, 'file')
        self.nc: Path = self._init_path(Path(self.output, 'nc'), config.nc)
        self.json: Path = self._init_path(Path(self.output, 'json'), config.json)
        self.txt: Path = self._init_path(Path(self.output, 'txt'), config.txt)
        self.png: Path = self._init_path(Path(self.output, 'png'), config.png)
        self.pickle: Path = self._init_path(Path(self.output, 'pickle'), config.pickle)
        self.zip: Path = self._init_path(Path(self.output, 'zip'), config.zip)

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

        self.default_author_weight: int = self._value_with_default(config.default_author_weight, 0)
        self.print_timing_messages: bool = self._value_with_default(config.print_timing_messages, False)

    def _value_with_default(self, val: Any, default: Any) -> Any:
        if val is None:
            return default
        else:
            return val

    def _init_path(
            self, default_path: Path, user_specified_path: str | None,
            path_type: Literal["dir", "file"] | None = "dir") -> Path:
        """Initialize the path to a newly produced file or an application directory
        to store newly produced files."""
        path = default_path if user_specified_path is None else Path(user_specified_path)
        if path_type == "dir" and not path.exists():
            path.mkdir(parents=True)
            print(f"Created directory '{path}'")
        return path

def create_obspack_release_name(config: Config, dt: datetime | None = None) -> str:
    elements = ['obspack', config.gas, '466']
    if config.obspack_product_name is not None:
        elements.append(config.obspack_product_name)
    elements.append(config.obspack_product_version)
    if dt is None:
        elements.append(datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    else:
        elements.append(dt.strftime("%Y%m%d"))
    return '_'.join(elements)
