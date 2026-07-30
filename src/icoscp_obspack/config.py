# Standard library imports.
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

# Related third party imports.
import yaml

# Local application/library specific imports.
from icoscp_obspack.citation import doi_citation

YAML_CONFIG = '../config.yml'


@dataclass(frozen=True)
class GasSpec:
    """Constants describing one of the gases the application supports."""
    conversion_factor: float
    calibration_scale: str
    plot_gas_label: str
    plot_unit_label: str
    plot_limy: tuple[int, int]


# The gases the application supports. Adding an entry here is not sufficient on its own:
# `specs_per_gas` and `first_dataset_id` in metadata_and_data_processing.py, and the object
# specifications in data_writer.py, need a matching entry as well.
GAS_SPECS: dict[str, GasSpec] = {
    'co2': GasSpec(1e-6, 'WMO CO2 X2019', 'CO${_2}$', '[µmol/mol]', (380, 460)),
    'ch4': GasSpec(1e-9, 'WMO X2004A', 'CH${_4}$', '[nmol/mol]', (1800, 2500)),
    'n2o': GasSpec(1e-9, 'NOAA-2006A', 'N${_2}$O', '[nmol/mol]', (315, 370)),
    'co': GasSpec(1e-9, 'WMO X2014A', 'CO', '[nmol/mol]', (0, 600)),
}


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

        # Reject an unsupported gas before any other work is done, so that the failure is
        # reported here rather than as a missing attribute much later in the run.
        if config.gas not in GAS_SPECS:
            possible_values = ', '.join(f"'{gas}'" for gas in GAS_SPECS)
            raise ValueError(f'Invalid gas: {config.gas}.\nPossible values are {possible_values}.')
        gas_spec = GAS_SPECS[config.gas]

        # Directories to be created by `create_output_directories()`. Collected while the paths
        # below are resolved, so that constructing a Config does not touch the filesystem.
        self._directories_to_create: list[Path] = []

        self.gas: str = config.gas
        self.doi: str = config.doi
        self.all_gases_obspack_doi: str = config.all_gases_obspack_doi
        self.dois_for_default_citations: list[str] = config.dois_for_default_citations
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

        self.conversion_factor: float = gas_spec.conversion_factor
        self.calibration_scale: str = gas_spec.calibration_scale
        self.plot_gas_label: str = gas_spec.plot_gas_label
        self.plot_unit_label: str = gas_spec.plot_unit_label
        self.plot_limy: tuple[int, int] = gas_spec.plot_limy

        self.default_author_weight: int = self._value_with_default(config.default_author_weight, 0)
        self.print_timing_messages: bool = self._value_with_default(config.print_timing_messages, False)

    @cached_property
    def default_citations(self) -> list[str]:
        """Citation strings of the references included in all datasets from ICOS stations.

        Resolved on first use rather than in `__init__`, because fetching them requires one
        network request per DOI and not every entry point needs them.
        """
        return [doi_citation(doi) for doi in self.dois_for_default_citations]

    def create_output_directories(self) -> None:
        """Create the application's directories.

        Called explicitly by the entry points so that merely constructing a `Config` — in a
        test, or in an entry point that only reads existing output — has no side effects.
        """
        for path in self._directories_to_create:
            if not path.exists():
                path.mkdir(parents=True)
                print(f"Created directory '{path}'")

    def _value_with_default(self, val: Any, default: Any) -> Any:
        if val is None:
            return default
        else:
            return val

    def _init_path(
            self, default_path: Path, user_specified_path: str | None,
            path_type: Literal["dir", "file"] | None = "dir") -> Path:
        """Resolve the path to a newly produced file or an application directory to store
        newly produced files. Directories are only recorded here; `create_output_directories()`
        creates them."""
        path = default_path if user_specified_path is None else Path(user_specified_path)
        if path_type == "dir":
            self._directories_to_create.append(path)
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
