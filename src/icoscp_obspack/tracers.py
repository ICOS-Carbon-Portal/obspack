"""Per-tracer descriptors.

A single place capturing everything that varies between the tracers the application supports:
data object specifications, the source columns holding the measured value and its standard
deviation, the units and wording of the netCDF `value` variable, the unit conversion, the
calibration scale, the dataset ID block, the plot labels and the ObsPack object specification
used when uploading individual datasets.

Adding a tracer means adding a descriptor to `TRACERS` and nothing else: the rest of the
application reads these fields rather than branching on the tracer's identity.
"""
# Standard library imports.
from dataclasses import dataclass

CPMETA = 'http://meta.icos-cp.eu/resources/cpmeta/'

# One FastTrack specification is shared by CO2, CH4, N2O and CO. Despite its name, each
# object still holds a single tracer; it is the specification that does not distinguish them, so
# the tracer has to be read from the file name, whose last underscore-separated token before the
# archive extension names it ('..._WAO_10.0_CTS_CO2.zip'). Tracers whose 'fasttrack' spec is this
# one need that disambiguation, the others do not.
FASTTRACK_SPEC = f'{CPMETA}atcGHGFastTrackNRTDataObject'

# ICOS data release level per data type. Shared by all tracers.
DATA_LEVEL_PER_TYPE: dict[str, int] = {'historic': 0, 'L2': 2, 'fasttrack': 15, 'nrt': 1}

# Flags indicating data to be kept if the configuration parameter 'use_flags' is True,
# depending on the ICOS data level of the dataset.
GOOD_FLAGS_PER_TYPE: dict[str, list[str]] = {
    'historic': ['O', 'U'],
    'L2': ['O', 'U'],
    'fasttrack': ['O', 'U'],
    'nrt': ['U']}

# Flag given to a row whose measured value is a sentinel but whose flag is good, an inconsistency
# found in some source files. 'K' is 'bad after manual quality check', as opposed to 'N', 'bad
# before manual quality check'.
SENTINEL_VALUE_FLAG = 'K'

# How each data type is referred to in the metadata of individual datasets.
DATA_TYPE_DESCRIPTIONS: dict[str, str] = {
    'historic': 'historical PI QCed data',
    'L2': 'ICOS Level 2 data',
    'fasttrack': 'ICOS FastTrack data',
    'nrt': 'ICOS NRT data'}


@dataclass(frozen=True)
class Sentinel:
    """The value a source column holds in place of a missing measurement."""

    value: float
    # Whether the column also holds genuine negative values. Where it does, a negative value
    # that merely looks like a sentinel (-9.9 for a Delta-14C, for instance) may well be a real
    # measurement, so only `value` itself is treated as missing there.
    negatives_are_valid: bool = False


# Columns written to the product that carry a sentinel in every tracer that has them. Keys are
# the source column names.
COMMON_SENTINELS: dict[str, Sentinel] = {
    'LTR': Sentinel(-999.99),
    'CMR': Sentinel(-999.99),
    # A bias, legitimately negative.
    'STTB': Sentinel(-999.99, negatives_are_valid=True),
    'NbPoints': Sentinel(-9),
}


@dataclass(frozen=True)
class Tracer:
    """Everything the application needs to know about one of the tracers it supports."""

    # Identity. Used as the configuration value, the output directory, the first component of
    # every produced file name and the 'dataset_parameter' netCDF attribute.
    key: str
    # Source columns holding the measured value and its standard deviation. Renamed to 'Meas'
    # and 'Stdev' when a data file is read.
    value_column: str
    std_column: str
    # Data type -> data object specification URI.
    specs: dict[str, str]
    # Base of the unique per-dataset ID counter in the ObsPack product.
    first_dataset_id: int
    # Source values are multiplied by this before being written to the netCDF file.
    conversion_factor: float
    # Whether negative values are physically impossible and should be set to NaN. True for mole
    # fractions, False for radon activity concentrations, which are near zero and noisy, and for
    # Delta-14C, which is routinely negative. Sentinels are removed beforehand, independently of
    # this; see `sentinels`.
    clip_negatives: bool
    # Units of the 'value' variable, and of every other variable expressed in the same units
    # ('value_std_dev', 'icos_LTR', 'icos_SMR', 'icos_STTB').
    value_units: str
    # CF standard name of the 'value' variable. An empty string means that no standard name
    # applies and that the attribute is left out of the netCDF file altogether.
    value_standard_name: str
    value_long_name: str
    value_comment: str
    # WMO GAW (or other) calibration scale. An empty string means that the tracer has none, in
    # which case the scale is left out of the metadata rather than reported as empty.
    calibration_scale: str
    # Warning about a change of calibration scale, reported as the 'warning_dataset_scale'
    # netCDF attribute. Empty for every tracer whose scale has not changed.
    scale_warning: str
    # Name of the measured species as it appears in the metadata of individual datasets.
    gas_species: str
    # The measured quantity, as it appears in the comment of individual datasets, fitting in
    # 'observational timeseries in netCDF format of {metadata_quantity} collected at ...'.
    metadata_quantity: str
    # Keyword attached to individual datasets, describing the measured quantity.
    metadata_keyword: str
    # Specification of the ObsPack result objects, used when uploading individual datasets.
    obspack_obj_spec: str
    plot_gas_label: str
    plot_unit_label: str
    plot_limy: tuple[float, float]
    # Source column name -> the sentinel it holds in place of a missing value, for every column
    # written to the product. One sentinel per column, as observed across every ATC data object
    # of the L2-2026.1 release; anything else that looks like one is reported when read.
    sentinels: dict[str, Sentinel]


def _greenhouse_gas(
        key: str, capitalized_key: str, spelled_out_name: str, conversion_factor: float,
        calibration_scale: str, obspack_obj_spec: str, plot_gas_label: str, plot_unit_label: str,
        plot_limy: tuple[float, float], first_dataset_id: int, scale_warning: str = '') -> Tracer:
    """Build the descriptor of a greenhouse gas measured as a dry air mole fraction.

    The four greenhouse gases share their whole shape: the value column is named after the gas,
    the data is available as all four data types, the FastTrack specification is the common one
    and the values are mole fractions expressed in mol mol-1.
    """
    return Tracer(
        key=key,
        value_column=key,
        std_column='Stdev',
        specs={
            'historic': f'{CPMETA}atc{capitalized_key}Product',
            'L2': f'{CPMETA}atc{capitalized_key}L2DataObject',
            'fasttrack': FASTTRACK_SPEC,
            'nrt': f'{CPMETA}atc{capitalized_key}NrtGrowingDataObject'},
        first_dataset_id=first_dataset_id,
        conversion_factor=conversion_factor,
        clip_negatives=True,
        value_units='mol mol-1',
        value_standard_name=f'mole_fraction_of_{spelled_out_name}_in_dry_air',
        value_long_name='measured_mole_fraction_of_trace_gas_in_dry_air',
        value_comment='mole per mole of dry air',
        calibration_scale=calibration_scale,
        scale_warning=scale_warning,
        gas_species=key.upper(),
        metadata_quantity=f'ambient mole fraction of {key.upper()} in dry air',
        metadata_keyword=f'atmospheric dry air {key} mole fraction',
        obspack_obj_spec=obspack_obj_spec,
        plot_gas_label=plot_gas_label,
        plot_unit_label=plot_unit_label,
        plot_limy=plot_limy,
        sentinels={key: Sentinel(-999.99), 'Stdev': Sentinel(-9.99), **COMMON_SENTINELS})


CO2_SCALE_WARNING = (
    'In Feb 2021, NOAA updated the WMO CO2 scale from version X2007 to X2019 (Hall et al., 2021).'
    ' The X2019 scale supersedes all previous versions of the WMO scale and is used in this GV+'
    ' release. Values contributed on scales other than X2019 have been adjusted by either known'
    ' scale offsets or with the known X2019 to X2007 relationship to account for changes'
    ' in the scale relationship caused by the X2019 revision.')

# The tracers the application supports. Adding an entry here is all that is needed: no other
# module branches on the identity of a tracer.
TRACERS: dict[str, Tracer] = {
    'co2': _greenhouse_gas(
        'co2', 'Co2', 'carbon_dioxide', 1e-6, 'WMO CO2 X2019', f'{CPMETA}ObspackTimeSerieResult',
        'CO${_2}$', '[µmol/mol]', (380, 460), 1000, scale_warning=CO2_SCALE_WARNING),
    'ch4': _greenhouse_gas(
        'ch4', 'Ch4', 'methane', 1e-9, 'WMO X2004A', f'{CPMETA}ObspackCH4TimeSeriesResult',
        'CH${_4}$', '[nmol/mol]', (1800, 2500), 2000),
    'n2o': _greenhouse_gas(
        'n2o', 'N2o', 'nitrous_oxide', 1e-9, 'NOAA-2006A', f'{CPMETA}ObspackN2oTimeSeriesResult',
        'N${_2}$O', '[nmol/mol]', (315, 370), 3000),
    'co': _greenhouse_gas(
        'co', 'Co', 'carbon_monoxide', 1e-9, 'WMO X2014A', f'{CPMETA}ObspackCOTimeSeriesResult',
        'CO', '[nmol/mol]', (0, 600), 4000),
}
