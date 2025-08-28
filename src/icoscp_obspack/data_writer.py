# Standard library imports.
import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Related third party imports.
import netCDF4
import numpy as np
import pandas as pd
from icoscp_core.icos import meta
from icoscp_core.metacore import Station
from icoscp_core.sparql import BoundUri, SparqlResults

# Local application/library specific imports.
from icoscp_obspack.citation import ContributorWithWeight
from icoscp_obspack.config import Config
from icoscp_obspack.utils import extract_temporal_components, get_hash_sum, timeit, year_fraction


@dataclass(frozen=True)
class StationExtraInfo:
    icos_id: str
    icos_labeled: str
    oscar_id: str
    lab_id: int
    lab_name: str
    timezone: float


@dataclass(frozen=True)
class NetcdfFileInfoForUploader:
    filename: str
    folder: Path
    station: str
    sampling_height: float
    hash: list[str]
    handle: str


class DataWriter:
    def __init__(
            self, config: Config, filename: str, data: pd.DataFrame,
            station: Station, station_extra_info: StationExtraInfo, height: float,
            contributors: list[ContributorWithWeight], citations: list[str],
            nc_cnt: int, row_counter: int, hashsums: list[str],
            dataset_creation_data: dt.datetime, obspack_creation_date: str,
            obspack_name: str, obspack_citation: str) -> None:
        self.config = config
        self.counter = row_counter
        self.obspack_creation_date = obspack_creation_date
        self.dataset_creation_data = dataset_creation_data
        self.filename = filename
        self.path_to_netcdf_file = Path(self.config.nc, f'{filename}.nc')
        self.data = data
        self.height = height
        self.station = station
        self.station_extra_info = station_extra_info
        self.contributor_uris = [contributor.uri for contributor in contributors]
        self.persons = ' AND '.join([
            f'{contributor.first_name} {contributor.last_name}' for contributor in contributors])
        self.citations = citations
        self.nc_cnt = nc_cnt
        self.hashsums = hashsums
        self.netcdf_dataset = netCDF4.Dataset(
            self.path_to_netcdf_file, 'w', format='NETCDF4', clobber=True)
        self.obspack_name = obspack_name
        self.obspack_citation = obspack_citation

    def produce_files(self) -> None:
        """Produce the netCDF and CSV files."""
        start_time = dt.datetime.now(dt.timezone.utc)
        variables = self._calculate_variables()
        time_after_calculating_variables = timeit(start_time, f'    Calculate variables for {self.filename}', self.config.print_timing_messages)
        self._initialize_netcdf()
        time_after_initializing_netcdf = timeit(time_after_calculating_variables, f'    Initialize netCDF for {self.filename}', self.config.print_timing_messages)
        self._fill_attributes()
        time_after_filling_attributes = timeit(time_after_initializing_netcdf, f'    Fill attributes for {self.filename}', self.config.print_timing_messages)
        self._fill_netcdf_variables(variables)
        time_after_filling_variables = timeit(time_after_filling_attributes, f'    Fill netCDF variables for {self.filename}', self.config.print_timing_messages)
        self.netcdf_dataset.sync()
        time_after_syncing_netcdf = timeit(time_after_filling_variables, f'    Sync netCDF for {self.filename}', self.config.print_timing_messages)
        self.netcdf_dataset.close()
        time_after_closing_netcdf = timeit(time_after_syncing_netcdf, f'    Close netCDF for {self.filename}', self.config.print_timing_messages)
        metadata_filename = Path(self.config.json, f'{self.filename}.json')
        with open(metadata_filename, 'w') as metadata_file:
            json.dump(self._generate_metadata(), metadata_file, indent=2)
        time_after_saving_metadata = timeit(time_after_closing_netcdf, f'    Write metadata for {self.filename}', self.config.print_timing_messages)
        if self.config.do_txt:
            self._produce_csv_file(variables)
        _ = timeit(time_after_saving_metadata, f'    Write CSV for {self.filename}', self.config.print_timing_messages)

    def _initialize_netcdf(self):
        self.netcdf_dataset.createDimension('time', self.data.shape[0])
        self.netcdf_dataset.createDimension('string_of_20chars', 20)
        self.netcdf_dataset.createDimension('calendar_components', 6)
        self.netcdf_dataset.createDimension('string_of_10chars', 10)
        self.netcdf_dataset.createDimension('string_of_200chars', 200)
        self.netcdf_dataset.createDimension('dim_concerns', 6)
        self.netcdf_dataset.createDimension('mip_nmodels', 17)
        self.netcdf_dataset.createDimension('nchar', 40)

        self.netcdf_dataset.createVariable('time', 'i4', ('time',), zlib=True)
        self.netcdf_dataset['time'].standard_name = 'time'
        self.netcdf_dataset['time'].longname = 'sample_time_in_seconds_since_january_1_1970'
        self.netcdf_dataset['time'].units = 'seconds since 1970-01-01T00:00:00Z'
        self.netcdf_dataset['time'].comment = (
            'POSIX time. Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported'
            ' at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging'
            ' intervals times are rounded down to the nearest second. Averaging interval is specified'
            ' through global attribute dataset_data_frequency (per hour)')

        self.netcdf_dataset.createVariable('start_time', 'i4', ('time',), zlib=True)
        self.netcdf_dataset['start_time'].longname = 'sample_time_in_seconds_since_january_1_1970'
        self.netcdf_dataset['start_time'].units = 'seconds since 1970-01-01T00:00:00Z'
        self.netcdf_dataset['start_time'].comment = (
            'POSIX time. Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported'
            ' at the beginning of the averaging interval (dataset_data_frequency). For uneven averaging'
            ' intervals times are rounded down to the nearest second. Averaging interval is specified'
            ' through global attribute dataset_data_frequency (per hour)')

        self.netcdf_dataset.createVariable('datetime', 'c', ('time', 'string_of_20chars',), zlib=True)
        self.netcdf_dataset['datetime'].longname = 'air_sample_date_and_time_in_UTC'
        self.netcdf_dataset['datetime'].comment = (
            'Air sample date and time in UTC ISO 8601 format. Time-averaged values are reported at'
            ' the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging'
            ' intervals times are rounded down to the nearest second. Averaging interval is specified'
            ' through global attribute dataset_data_frequency (per hour)')

        self.netcdf_dataset.createVariable('time_decimal', 'f8', ('time',), zlib=True)
        self.netcdf_dataset['time_decimal'].longname = 'sample_decimal_year_in_UTC'
        self.netcdf_dataset['time_decimal'].comment = (
            'Decimal year in UTC. Time-averaged values are reported at the midpoint of the averaging'
            ' interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to'
            ' the nearest second.')

        self.netcdf_dataset.createVariable(
            'time_components', 'i2', ('time', 'calendar_components',), fill_value=-9, zlib=True)
        self.netcdf_dataset['time_components'].longname = 'integer_components_of_UTC_date/time'
        self.netcdf_dataset['time_components'].order = 'year, month, day, hour, minute, second'
        self.netcdf_dataset['time_components'].comment = (
            'Calendar time components as integers. Times and dates are UTC. Time-averaged values are'
            ' reported at the midpoint of the averaging interval (dataset_data_frequency). For uneven'
            ' averaging intervals times are rounded down to the nearest second.')

        self.netcdf_dataset.createVariable(
            'solartime_components', 'i2', ('time', 'calendar_components',), fill_value=-9, zlib=True)
        self.netcdf_dataset['solartime_components'].longname = 'integer_components_of_local_solar_date/time'
        self.netcdf_dataset['solartime_components'].order = 'year, month, day, hour, minute, second'
        self.netcdf_dataset['solartime_components'].comment = (
            'Calendar local solar time components as integers. UTC time is converted to local solar'
            ' time based on longitude and day-of-year. Time-averaged values are reported at the midpoint'
            ' of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are'
            ' rounded down to the nearest second.')

        self.netcdf_dataset.createVariable('value', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['value'].long_name = 'measured_mole_fraction_of_trace_gas_in_dry_air'
        self.netcdf_dataset['value'].standard_name = f'mole_fraction_of_{self.config.gas}_in_dry_air'
        self.netcdf_dataset['value'].units = 'mol mol-1'
        self.netcdf_dataset['value'].comment = 'mole per mole of dry air'
        self.netcdf_dataset['value'].scale_comment = self.config.calibration_scale

        self.netcdf_dataset.createVariable('nvalue', 'i', ('time',), fill_value=-9, zlib=True)
        self.netcdf_dataset['nvalue'].long_name = 'number_of_measurements_contributing_to_reported_value'
        self.netcdf_dataset['nvalue'].comment = (
            'Number of individual measurements used to compute reported value.'
            ' See provider_comment if available.')

        self.netcdf_dataset.createVariable('value_std_dev', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['value_std_dev'].long_name = 'standard_deviation_in_reported_value'
        self.netcdf_dataset['value_std_dev'].units = 'mol mol-1'
        self.netcdf_dataset['value_std_dev'].comment = (
            'This is the standard deviation of the reported mean value when nvalue is greater than 1.'
            ' See provider_comment if available.')

        self.netcdf_dataset.createVariable('latitude', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['latitude'].long_name = 'sample_latitude_in_decimal_degrees'
        self.netcdf_dataset['latitude'].units = 'decimal degrees north (-90..90)'
        self.netcdf_dataset['latitude'].comment = 'Latitude at which air sample was collected.'

        self.netcdf_dataset.createVariable('longitude', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['longitude'].long_name = 'sample_longitude_in_decimal_degrees'
        self.netcdf_dataset['longitude'].units = 'decimal degrees east (-180..180)'
        self.netcdf_dataset['longitude'].comment = 'Longitude at which air sample was collected.'

        self.netcdf_dataset.createVariable('altitude', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['altitude'].long_name = 'sample_altitude_in_meters_above_sea_level'
        self.netcdf_dataset['altitude'].units = 'meters above sea level (masl)'
        self.netcdf_dataset['altitude'].comment = \
            'Altitude (surface elevation plus sample intake height) at which air sample was collected'

        self.netcdf_dataset.createVariable('intake_height', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['intake_height'].long_name = \
            'Height above ground at which air sample was collected'
        self.netcdf_dataset['intake_height'].units = 'meters above ground level (magl)'
        self.netcdf_dataset['intake_height'].comment = \
            'Sample intake height in meters above ground level (magl)'

        self.netcdf_dataset.createVariable('qc_flag', 'c', ('time',), fill_value='-', zlib=True)
        self.netcdf_dataset['qc_flag'].long_name = 'quality_control_flag'
        self.netcdf_dataset['qc_flag'].comment = (
            '- Flag U = data correct before manual quality control - Flag O = data correct after manual'
            ' quality control, other flags denote incorrect data. Data processing at ICOS ATC is described'
            ' in [Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.')

        self.netcdf_dataset.createVariable('quality_id', 'i', ('time',), fill_value=-9, zlib=True)
        self.netcdf_dataset['quality_id'].long_name = 'quality_id'
        self.netcdf_dataset['quality_id'].comment = (
            'Unique ID linking to the QC provenance - Data processing at ICOS ATC is described in'
            ' [Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.')

        self.netcdf_dataset.createVariable('instrument', 'i', ('time',), fill_value=-9, zlib=True)
        self.netcdf_dataset['instrument'].long_name = 'instrument_ID_to_detect_atmospheric_parameter'
        self.netcdf_dataset['instrument'].comment = \
            'Instrument ID used to detect atmospheric parameter. See provider_comment if available.'
        self.netcdf_dataset['instrument'].provider_comment = \
            'This variable is the ICOS provided Instrument ID'

        self.netcdf_dataset.createVariable('icos_datalevel', 'b', ('time',), fill_value='255', zlib=True)
        self.netcdf_dataset['icos_datalevel'].long_name = 'icos_data_release_level'
        self.netcdf_dataset['icos_datalevel'].comment = (
            'Level 0 means pre-ICOS or non-ICOS data (processing by PI); Level 1 means NRT=near real-time'
            ' data (Automatic Quality Control by ICOS ATC) delay max 24 hrs; Level 2 means final quality'
            ' data (Manual and automatic QC by PI and ATC - Data processing at ICOS ATC is described in'
            ' [Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.')

        self.netcdf_dataset.createVariable('icos_LTR', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['icos_LTR'].long_name = 'icos_long_term_repeatability'
        self.netcdf_dataset['icos_LTR'].units = 'mol mol-1'
        self.netcdf_dataset['icos_LTR'].comment = (
            'Analytical uncertainty parameters LTR, CMR and STTB are described in [Yver Kwok et al, 2015]'
            ' https://doi.org/10.5194/amt-8-3867-2015')

        self.netcdf_dataset.createVariable('icos_SMR', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['icos_SMR'].long_name = 'icos_continuous_measurement_repeatability'
        self.netcdf_dataset['icos_SMR'].units = 'mol mol-1'
        self.netcdf_dataset['icos_SMR'].comment = (
            'Analytical uncertainty parameters LTR, CMR and STTB are described in [Yver Kwok et al, 2015]'
            ' https://doi.org/10.5194/amt-8-3867-2015')

        self.netcdf_dataset.createVariable('icos_STTB', 'f4', ('time',), fill_value=np.nan, zlib=True)
        self.netcdf_dataset['icos_STTB'].long_name = 'icos_short_term_target_bias'
        self.netcdf_dataset['icos_STTB'].units = 'mol mol-1'
        self.netcdf_dataset['icos_STTB'].comment = (
            'Analytical uncertainty parameters LTR, CMR and STTB are described in [Yver Kwok et al, 2015]'
            ' https://doi.org/10.5194/amt-8-3867-2015')

        self.netcdf_dataset.createVariable('obs_flag', 'b', ('time',), fill_value=1, zlib=True)
        self.netcdf_dataset['obs_flag'].long_name = 'obs_flag'
        self.netcdf_dataset['obs_flag'].units = 'binary'
        self.netcdf_dataset['obs_flag'].comment = (
            'Determined by data provider (1: large spatial scale representation; 0: local/regional'
            ' influence). The implementation of this flag is still being developed.')

        self.netcdf_dataset.createVariable('obspack_id', 'c', ('time', 'string_of_200chars',), zlib=True)
        self.netcdf_dataset['obspack_id'].long_name = 'obs_flag'
        self.netcdf_dataset['obspack_id'].comment = (
            'Unique identification string that distinguishes the data item from all other data items'
            ' both within an ObsPack product, and across any ObsPack data product. It includes obspack_name,'
            ' dataset_name, and obspack_num, with each field delimited by a tilde (~).')

        self.netcdf_dataset.createVariable('assimilation_concerns', 'b', ('time', 'dim_concerns'), zlib=True)
        self.netcdf_dataset['assimilation_concerns'].long_name = 'assimilation_concerns'
        self.netcdf_dataset['assimilation_concerns'].units = 'NA'
        self.netcdf_dataset['assimilation_concerns'].order = \
            'time window, representivity, variability, under review, wdcgg-background, scale_conversion'
        self.netcdf_dataset['assimilation_concerns'].comment = (
            'Values in this array indicate if the given observation has the assimilation concern defined'
            ' by each column. A value of 0 means that there is no concern or it is not known to exist,'
            ' and a non-zero value means that this concern does exist. Data suitable for a global scale'
            ' model in general will have a 0 in the time window, representivity, and variability columns'
            ' of this variable. The implementation of this variable is still being developed.')

        self.netcdf_dataset.createVariable('obs_num', 'i', ('time',), zlib=True)
        self.netcdf_dataset['obs_num'].long_name = 'unique_dataset_observation_number'
        self.netcdf_dataset['obs_num'].comment = \
            f'Unique observation number in this data set.  Range is from 1 to {self.data.shape[0] + 1}'

        self.netcdf_dataset.createVariable('obspack_num', 'i', ('time',), zlib=True)
        self.netcdf_dataset['obspack_num'].long_name = 'unique_ObsPack_observation_number'
        self.netcdf_dataset['obspack_num'].comment = (
            'Unique observation index number across all data sets in the ObsPack data product. '
            'Range is from 1 to max_obspack_num')

    def _fill_attributes(self):
        """
        Fill the attributes of the netCDF file.
        Most value are default and copied from Obspack V7 2021 and some need to be replaced
        with actual info before writing to netCDF.
        """
        if self.config.gas == 'co2':
            warning = (
                'In Feb 2021, NOAA updated the WMO CO2 scale from version X2007 to X2019 (Hall et al., 2021).'
                ' The X2019 scale supersedes all previous versions of the WMO scale and is used in this GV+'
                ' release. Values contributed on scales other than X2019 have been adjusted by either known'
                ' scale offsets or with the known X2019 to X2007 relationship to account for changes'
                ' in the scale relationship caused by the X2019 revision.')
        else:
            warning = ''

        attributes: dict[str, Any] = {
            'site_code': self.station.id,
            'site_name': self.station.org.name,
            'site_country': self.station.countryCode,
            'site_latitude': self.station.location.lat if self.station.location is not None else np.nan,
            'site_longitude': self.station.location.lon if self.station.location is not None else np.nan,
            'site_elevation': (
                self.station.location.alt
                if self.station.location is not None and self.station.location.alt is not None
                else np.nan),
            'site_elevation_unit': 'masl',
            'site_position_comment': (
                'This is the nominal location of the site. The sampling location at many sites has changed'
                ' over time, and we report here the most recent nominal location. The actual sampling'
                ' location for each observation is not necessarily the site location. The sampling locations'
                ' for each observation are reported in the latitude, longitude, and altitude variables.'),
            'site_utc2lst': self.station_extra_info.timezone,
            'site_utc2lst_comment': (
                'Add site_utc2lst hours to convert a time stamp in UTC (Coordinated Universal Time) to LST'
                ' (Local Standard Time).'),
            'site_url': self.station.org.self.uri,
            'site_oscar_id': self.station_extra_info.oscar_id,
            'warning_dataset_scale': warning,
            'dataset_creation_date': self.dataset_creation_data.isoformat().replace('+00:00', 'Z'),
            'dataset_num': self.nc_cnt,
            'dataset_name': self.filename,
            'dataset_globalview_prefix': f'{self.station.id}_{self.station_extra_info.lab_id}C0',
            'dataset_process': "PassThru",
            'dataset_alternative_names': 'NA',
            'dataset_alternative_names_description': (
                'The attribute dataset_alternative_names is used to identify all other dataset names'
                ' that have been used for the record in this dataset. To obtain the full record for'
                ' this dataset please use all alternatively named datasets that appear in this ObsPack'
                ' product and the corresponding release of other ObsPacks if applicable.'),
            'dataset_alternative_names_comment': '',
            'dataset_parameter': self.config.gas,
            'dataset_project': 'surface-insitu or tower-insitu',
            'dataset_platform': 'fixed',
            'dataset_map': (
                f'https://meta.icos-cp.eu/station/?station=/resources/stations/AS_{self.station.id}'
                '&icon=https://static.icos-cp.eu/share/stations/icons/as.png'),
            'dataset_selection': f'all hourly data from {self.height} magl intake',
            'dataset_selection_tag': f'allvalid-{self.height}magl',
            'dataset_comment': (
                'Please note that some datasets included in past Obspack releases are now provided'
                ' by the ICOS program. The valid data selection scheme for ICOS datasets may differ'
                ' significantly from the selection scheme provided previously by contributing laboratories.'),
            'dataset_contains_ICOS_L1_and_or_L2_data': self.station_extra_info.icos_labeled,
            'dataset_calibration_scale': self.config.calibration_scale,
            'dataset_start_date': self.data.index[0].isoformat().replace('+00:00', 'Z'),
            'dataset_stop_date': self.data.index[-1].isoformat().replace('+00:00', 'Z'),
            'dataset_data_frequency': 1.,
            'dataset_data_frequency_unit': 'hour',
            'dataset_time_window_lst': '0-23',
            'dataset_time_window_utc': '0-23',
            'dataset_time_window_exclusion': 'F',
            'dataset_intake_ht': self.height,
            'dataset_intake_ht_unit': 'magl',
            'dataset_description': (
                'This data package is intended for use in carbon cycle inverse modeling, model evaluation,'
                ' and satellite validation studies. Please report errors and send comments'
                ' regarding this product to the ObsPack originators. Please read carefully the ObsPack'
                ' Fair Use statement and cite appropriately. DOI metadata for this product are available'
                f' at https://search.datacite.org/works/{self.config.doi}.'),
            'dataset_usage_url': f'https://doi.org/{self.config.doi}',
            'dataset_usage_description': (
                'In addition to this product\'s citation we ask that you please cite the following'
                ' provider citations when using data from this dataset.'),
            'dataset_provider_citation_total': str(len(self.citations))}

        for i in range(0, len(self.citations)):
            attributes.update({f'dataset_provider_citation_{i + 1}': self.citations[i]})

        more_attributes: dict[str, Any] = {
            'dataset_provider_license': (
                'DATA POLICY: ICOS DATA is licensed under a Creative Commons Attribution 4.0 international'
                ' licence (http://creativecommons.org/licenses/by/4.0/.The ICOS data licence is described'
                ' at https://data.icos-cp.eu/licence.'),
            'dataset_provider_license_url': 'http://creativecommons.org/licenses/by/4.0/',
            'dataset_reference_total_listed': 0,
            'dataset_contribution': (
                f'These data are provided by ICOS-RI AND {self.station_extra_info.lab_name} AND ICOS ATC,'
                f' CAL, Carbon Portal. Principal investigators and contributors include {self.persons}.'),
            'obspack_variables_and_attributes': (
                'ObsPack variables and attributes are described at '
                'www.gml.noaa.gov/ccgg/obspack/documentation.html#MetaData'),
            'obspack_name': self.obspack_name,
            'obspack_description': (
                'This data file is part of a data package called Obspack that is intended for use in carbon'
                ' cycle inverse modeling, model evaluation, and satellite validation studies. Please report'
                ' errors and send comments regarding this product to the ObsPack originators. Please read'
                ' carefully the ObsPack Fair Use statement and cite appropriately. DOI metadata for this'
                f' product are available at https://search.datacite.org/works/{self.config.doi}.'
                ' Please visit http://www.gml.noaa.gov/ccgg/obspack/ for more information.'),
            'obspack_creation_date': self.obspack_creation_date,
            'obspack_warning': (
                'Every effort is made to create the most accurate and precise data product possible.'
                ' Contributors reserve the right to make corrections to this product and data based'
                ' on recalibration of standard gases or for other reasons deemed scientifically justified.'
                ' Contributors to this product are not responsible for results and conclusions based on use'
                ' of this product without regard to this warning.'),
            'obspack_fair_use': (
                'This cooperative data product is made freely available to the scientific community and'
                ' is intended to stimulate and support carbon cycle modeling studies. We rely on the ethics'
                ' and integrity of the user to assure that each contributing national and university'
                ' laboratory receives fair credit for their work. Fair credit will depend on the nature of'
                ' the work and the requirements of the institutions involved. Your use of this data product'
                ' implies an agreement to contact each contributing laboratory for data sets used to discuss'
                ' the nature of the work and the appropriate level of acknowledgement. If this product is'
                ' essential to the work, or if an important result or conclusion depends on this product,'
                ' co-authorship may be appropriate. This should be discussed with the appropriate data'
                ' providers at an early stage in the work. Contacting the data providers is not optional;'
                ' if you use this data product, you must contact the applicable data providers. To help you'
                ' meet your obligation, the data product includes an e-mail distribution list of all data'
                ' providers. This data product must be obtained directly from the ICOS Data Portal at'
                ' https://data.icos-cp.eu/portal/ and we ask you to not re-distribute. In addition to'
                ' the conditions of fair use as stated above, users are requested to include the ObsPack'
                ' product citation in any publication or presentation using the product. The required'
                ' citation is included in every data product.'),
            'obspack_usage_policy': 'https://www.icos-cp.eu/data-services/about-data-portal/data-license',
            'obspack_data_license': 'https://creativecommons.org/licenses/by/4.0/',
            'obspack_identifier_link': f'https://doi.org/{self.config.doi}',
            'obspack_citation': self.obspack_citation,
            'Conventions': 'CF-1.7',
            'nc.institution': 'Unidata',
            'source': 'ICOS RI',
            'history': f'{self.dataset_creation_data.isoformat()} ICOS CP Obspack Python tool'
        }
        attributes.update(more_attributes)

        self.netcdf_dataset.setncatts(attributes)

    def _calculate_variables(self) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        timestamps = self.data.index.astype('int64') // 10**9 # Convert to seconds since epoch
        index_mid = self.data.index + dt.timedelta(seconds=1800)
        time_before_calculating_temporal_variables = dt.datetime.now(dt.timezone.utc)
        variables['start_time'] = timestamps
        variables['time'] = timestamps + 1800
        variables['datetime'] = [t.isoformat().replace('+00:00', 'Z') for t in index_mid]
        variables['time_decimal'] = [year_fraction(t) for t in index_mid]
        variables['time_components'] = [extract_temporal_components(i, 1800) for i in self.data.index]
        variables['solartime_components'] = [extract_temporal_components(i, 1800 + self.station_extra_info.timezone * 3600) for i in self.data.index]
        _ = timeit(time_before_calculating_temporal_variables, f'        Calculate time variables for {self.filename}', self.config.print_timing_messages)
        variables['value'] = self.data['Meas'].array
        variables['value_std_dev'] = self.data['Stdev'].array
        variables['nvalue'] = self.data['NbPoints'].array
        variables['latitude'] = self.station.location.lat if self.station.location is not None else np.nan
        variables['longitude'] = self.station.location.lon if self.station.location is not None else np.nan
        variables['altitude'] = (
            float(self.station.location.alt) + self.height
            if self.station.location is not None and self.station.location.alt is not None
            else np.nan)
        variables['intake_height'] = self.height
        variables['qc_flag'] = self.data['Flag'].array
        variables['icos_datalevel'] = self.data['Level'].array
        variables['icos_LTR'] = self.data['LTR'].array if 'LTR' in self.data.columns else np.zeros(self.data.shape[0])*np.nan
        variables['icos_SMR'] = self.data['CMR'].array if 'CMR' in self.data.columns else np.zeros(self.data.shape[0])*np.nan
        variables['icos_STTB'] = self.data['STTB'].array if 'STTB' in self.data.columns else np.zeros(self.data.shape[0])*np.nan
        variables['quality_id'] = self.data['QualityId'].array
        variables['instrument'] = self.data['InstrumentId'].array if 'InstrumentId' in self.data.columns else -1
        variables['obs_flag'] = 1
        variables['obs_num'] = np.arange(1, self.data.shape[0] + 1, 1)
        variables['obspack_num'] = np.arange(self.counter + 1, self.counter + self.data.shape[0] + 1, 1)
        variables['obspack_id'] = [
            f'{self.obspack_name}~{self.filename}~{self.counter + i + 1}' for i in range(self.data.shape[0])]
        variables['assimilation_concerns'] = 0
        return variables

    def _fill_netcdf_variables(self, variables: dict[str, Any]):
        string_dtypes = {'datetime': 'S20', 'obspack_id': 'S200'}
        for variable, values in variables.items():
            if variable in ['datetime', 'obspack_id']:
                self.netcdf_dataset[variable][:] = netCDF4.stringtochar(
                    np.array(values, dtype=string_dtypes[variable]))
            elif variable in ['value', 'value_std_dev', 'icos_LTR', 'icos_SMR', 'icos_STTB']:
                new_values = values*self.config.conversion_factor
                new_values[new_values < 0] = np.nan
                self.netcdf_dataset[variable][:] = new_values
            else:
                self.netcdf_dataset[variable][:] = values

    def _produce_csv_file(self, variables: dict[str, Any]):
        start_time = dt.datetime.now(dt.timezone.utc)
        order_of_variables = [
            'datetime', 'year', 'month', 'day', 'hour', 'minute', 'second',
            'time', 'start_time', 'time_decimal', 'value', 'value_std_dev', 'nvalue',
            'qc_flag', 'icos_datalevel', 'icos_LTR', 'icos_SMR', 'icos_STTB', 'quality_id', 'instrument',
            'latitude', 'longitude', 'altitude', 'intake_height', 'obs_num', 'obspack_num', 'obspack_id'
        ]
        index: pd.DatetimeIndex = self.data.index
        time_components: dict[str, Any] = {
            'year': index.year,
            'month': index.month,
            'day': index.day,
            'hour': index.hour,
            'minute': index.minute,
            'second': index.second
        }
        csv_data = pd.DataFrame(columns=order_of_variables)
        time_after_initializing_csv = timeit(start_time, f'        Initialize CSV data table for {self.filename}', self.config.print_timing_messages)
        for variable in order_of_variables:
            if variable in variables.keys():
                csv_data[variable] = variables[variable]
            elif variable in ['year', 'month', 'day', 'hour', 'minute', 'second']:
                csv_data[variable] = time_components[variable]
            else:
                print(f'Variable {variable} is not defined but is requested by the CSV file, skipping.')
        time_after_filling_csv = timeit(time_after_initializing_csv, f'        Fill CSV data table for {self.filename}', self.config.print_timing_messages)
        csv_path = Path(self.config.txt, f'{self.filename}.txt')
        skipped_variables = set(variables.keys()).difference(set(order_of_variables))
        header = self._create_txt_header(skipped_variables=skipped_variables)
        time_after_creating_csv_header = timeit(time_after_filling_csv, f'        Create header for CSV {self.filename}', self.config.print_timing_messages)
        with open(csv_path, 'w') as csv_file:
            for line in header:
                csv_file.write(f'{line}\n')
        time_after_writing_csv_header = timeit(time_after_creating_csv_header, f'        Write header for CSV {self.filename}', self.config.print_timing_messages)
        csv_data.to_csv(
            csv_path, mode='a', sep=' ', na_rep='-999999', header=True, index=False, float_format='%.5f')
        _ = timeit(time_after_writing_csv_header, f'        Write CSV data for {self.filename}', self.config.print_timing_messages)

    def _create_txt_header(self, skipped_variables: set[str]) -> list[str]:
        with open(self.config.header) as f:
            header_template = f.readlines()
        stream = os.popen(f'ncdump -h {self.path_to_netcdf_file.resolve()}')
        header_netcdf = stream.readlines()
        header_filtered: list[str] = []
        header_variables = [
            '#', '# ------------------------------------------------------------->>>>',
            '# VARIABLE ATTRIBUTES', '#']
        for line in header_netcdf:
            if line.startswith('\t\t'):
                cleaned_line = line.strip('\t\n; ')
                index_of_separator = cleaned_line.find(' = ')
                key = cleaned_line[:index_of_separator]
                val = cleaned_line[index_of_separator + 3:]
                if key.startswith(':'):
                    header_filtered.append(' = '.join([f'# {key[1:]}', val.strip('"')]))
                elif key.startswith('string :'):
                    header_filtered.append(' = '.join([f'# {key[8:]}', val.strip('"')]))
                elif key.split(':')[0] not in skipped_variables:
                    header_variables.append(' = '.join([f'# {key}', val.strip('"')]))
        header_variables.append('#')
        header_variables.append('# VARIABLE ORDER')
        header_variables.append('#')
        h_len = len(header_template) + len(header_filtered) + len(header_variables) + 1

        txt_header: list[str] = [f'# header_lines : {h_len}']
        for header_line in header_template:
            line = header_line.replace('\n', '')
            if 'doi_xxx' in line:
                line = line.replace('doi_xxx', self.config.doi)
            if 'citation_xxx' in line:
                line = line.replace('citation_xxx', self.obspack_citation)
            if 'obspack_xxx' in line:
                line = line.replace('obspack_xxx', self.obspack_name)
            if 'dataset_xxx' in line:
                line = line.replace('dataset_xxx', self.filename)
            txt_header.append(line)
        for line in header_filtered:
            txt_header.append(line)
        for line in header_variables:
            txt_header.append(line)
        return txt_header

    def _generate_metadata(self) -> dict[str, Any]:
        """Generate and upload metadata."""
        if self.config.gas == 'co2':
            obj_spec = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackTimeSerieResult'
        elif self.config.gas == 'ch4':
            obj_spec = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackCH4TimeSeriesResult'
        elif self.config.gas == 'n2o':
            obj_spec = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackN2oTimeSeriesResult'
        else:
            obj_spec = ''

        hashsum_of_previous_version = get_prev_by_name(filename=self.path_to_netcdf_file.name)

        metadata_for_upload: dict[str, Any] = {
            "submitterId": "CP",
            "hashSum": get_hash_sum(path=self.path_to_netcdf_file),
            "fileName": self.path_to_netcdf_file.name,
            "specificInfo": {
                "station": self.station.org.self.uri,
                "samplingHeight": self.height,
                "production": {
                    "creator": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "contributors": self.contributor_uris,
                    "hostOrganization": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "comment": (
                        "European Obspack observational timeseries in netcdf format of ambient mole"
                        f" fraction of {self.config.gas} in dry air calibrated using the WMO GAW calibration"
                        f" scale {self.config.calibration_scale}, composed of (all whenever available)"
                        f" historical PI QCed data, ICOS Level 2 data and ICOS NRT data"),
                    "creationDate": self.dataset_creation_data.isoformat().replace('+00:00', 'Z'),
                    "sources": self.hashsums
                }
            },
            "objectSpecification": obj_spec,
            "preExistingDoi": self.config.doi,
            "references": {
                "autodeprecateSameFilenameObjects": True,
                "keywords": [
                    self.config.calibration_scale, f"atmospheric dry air {self.config.gas} mole fraction"]
            }
        }

        if hashsum_of_previous_version is not None:
            metadata_for_upload["isNextVersionOf"] = [hashsum_of_previous_version]

        return metadata_for_upload


def get_prev_by_name(filename: str) -> str | None:
    query = f"""
    PREFIX cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
    SELECT ?dobj
    WHERE {{
        VALUES ?spec {{
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackTimeSerieResult>
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackCH4TimeSeriesResult>
            <http://meta.icos-cp.eu/resources/cpmeta/ObspackN2oTimeSeriesResult>
        }}
        ?dobj cpmeta:hasObjectSpec ?spec .
        ?dobj cpmeta:hasName ?fileName .
        ?dobj cpmeta:hasSizeInBytes ?size .
        FILTER(STRSTARTS(str(?fileName), "{filename}"))
        FILTER NOT EXISTS {{[] cpmeta:isNextVersionOf ?dobj}}
    }}
    """
    sparql_res: SparqlResults = meta.sparql_select(query=query)
    if sparql_res.bindings:
        dobj_value = sparql_res.bindings[0]['dobj']
        assert isinstance(dobj_value, BoundUri)
        prev_uri = dobj_value.uri
        return prev_uri.split('/')[-1]
    else:
        print(f'No previous version found for data object of file "{filename}".')
        return None
