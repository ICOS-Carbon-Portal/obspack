# Standard library imports.
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

# Related third party imports.
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# Local application/library specific imports.
from icoscp_obspack.config import Config
from icoscp_obspack.utils.utils import doi_citation, get_hash_sum, get_prev_by_name

def write_nc(c, f_name, df, station, citations, settings, persons='', hgh=150,
             factor=1e6, calib_scale='WMO CO2 X2019', lab_id=466, nc_cnt=0,
             doi_cite='PEKQ-M4T1'):
    """Write measurements' data as ObsPack NetCDF file."""

    # for testing purposes you can truncate a data file to max 100 rows
    # df = df[:99]

    dlen = len(df.index)
    nc_name = Path(c.nc, f'{f_name}.nc')
    ds = netCDF4.Dataset(nc_name, 'w', format='NETCDF4', clobber=True)
    #    try:
    # create dimensions
    time = ds.createDimension('time', dlen)
    s20 = ds.createDimension('string_of_20chars', 20)
    cal_6 = ds.createDimension('calendar_components', 6)
    s10 = ds.createDimension('string_of_10chars', 10)
    s200 = ds.createDimension('string_of_200chars', 200)
    dim6 = ds.createDimension('dim_concerns', 6)
    mip17 = ds.createDimension('mip_nmodels', 17)
    ch40 = ds.createDimension('nchar', 40)

    # add variables
    time = ds.createVariable('time', 'i4', ('time',), zlib=True)
    time.standard_name = 'time'
    time.longname = 'sample_time_in_seconds_since_january_1_1970'
    time.units = 'seconds since 1970-01-01T00:00:00Z'
    time.comment = 'POSIX time.  Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported' \
                   ' at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                   ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    # add variables
    start_time = ds.createVariable('start_time', 'i4', ('time',), zlib=True)
    start_time.longname = 'sample_time_in_seconds_since_january_1_1970'
    start_time.units = 'seconds since 1970-01-01T00:00:00Z'
    start_time.comment = 'POSIX time.  Number of seconds since January 1, 1970 in UTC. Time-averaged values are reported' \
                         ' at the beginning of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                         ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    datetime = ds.createVariable('datetime', 'c',
                                 ('time', 'string_of_20chars',), zlib=True)
    datetime.longname = 'air_sample_date_and_time_in_UTC'
    datetime.comment = 'Air sample date and time in UTC ISO 8601 format. Time-averaged values are reported at' \
                       ' the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the' \
                       ' nearest second. Averaging interval is specified through global attribute dataset_data_frequency (per hour)'

    time_decimal = ds.createVariable('time_decimal', 'f8', ('time',),
                                     zlib=True)
    time_decimal.longname = 'sample_decimal_year_in_UTC'
    time_decimal.comment = 'Decimal year in UTC. Time-averaged values are reported at the midpoint of the averaging ' \
                           'interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to the nearest second.'

    time_components = ds.createVariable('time_components', 'i2',
                                        ('time', 'calendar_components',),
                                        fill_value=-9, zlib=True)
    time_components.longname = 'integer_components_of_UTC_date/time'
    time_components.order = 'year, month, day, hour, minute, second'
    time_components.comment = 'Calendar time components as integers.  Times and dates are UTC. Time-averaged values are ' \
                              'reported at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to ' \
                              'the nearest second.'

    solartime_components = ds.createVariable('solartime_components', 'i2',
                                             ('time', 'calendar_components',),
                                             fill_value=-9, zlib=True)
    solartime_components.longname = 'integer_components_of_local_solar_date/time'
    solartime_components.order = 'year, month, day, hour, minute, second'
    solartime_components.comment = 'Calendar local solar time components as integers.  UTC time is converted to local solar ' \
                                   'time based on longitude and day-of-year.  Time-averaged values are ' \
                                   'reported at the midpoint of the averaging interval (dataset_data_frequency). For uneven averaging intervals times are rounded down to ' \
                                   'the nearest second.'

    value = ds.createVariable('value', 'f4', ('time',), fill_value=np.nan,
                              zlib=True)
    value.long_name = 'measured_mole_fraction_of_trace_gas_in_dry_air'
    value.standard_name = 'mole_fraction_of_' + c.gas + '_in_dry_air'
    value.units = 'mol mol-1'
    value.comment = 'mole per mole of dry air'
    value.scale_comment = calib_scale

    nvalue = ds.createVariable('nvalue', 'i', ('time',), fill_value=-9,
                               zlib=True)
    nvalue.long_name = 'number_of_measurements_contributing_to_reported_value'
    nvalue.comment = 'Number of individual measurements used to compute reported value. See provider_comment' \
                     ' if available.'

    value_std_dev = ds.createVariable('value_std_dev', 'f4', ('time',),
                                      fill_value=np.nan, zlib=True)
    value_std_dev.long_name = 'standard_deviation_in_reported_value'
    value_std_dev.units = 'mol mol-1'
    value_std_dev.comment = 'This is the standard deviation of the reported mean value when nvalue is greater than 1' \
                            '. See provider_comment if available.'

    latitude = ds.createVariable('latitude', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    latitude.long_name = 'sample_latitude_in_decimal_degrees'
    latitude.units = 'decimal degrees north (-90..90)'
    latitude.comment = 'Latitude at which air sample was collected.'

    longitude = ds.createVariable('longitude', 'f4', ('time',),
                                  fill_value=np.nan, zlib=True)
    longitude.long_name = 'sample_longitude_in_decimal_degrees'
    longitude.units = 'decimal degrees east (-180..180)'
    longitude.comment = 'Longitude at which air sample was collected.'

    altitude = ds.createVariable('altitude', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    altitude.long_name = 'sample_altitude_in_meters_above_sea_level'
    altitude.units = 'meters above sea level (masl)'
    altitude.comment = 'Altitude (surface elevation plus sample intake height) at which air sample was collected'

    intake_height = ds.createVariable('intake_height', 'f4', ('time',),
                                      fill_value=np.nan, zlib=True)
    intake_height.long_name = 'Height above ground at which air sample was collected'
    intake_height.units = 'meters above ground level (magl)'
    intake_height.comment = 'Sample intake height in meters above ground level (magl)'

    qc_flag = ds.createVariable('qc_flag', 'c', ('time',), fill_value='-',
                                zlib=True)
    qc_flag.long_name = 'quality_control_flag'
    qc_flag.comment = '- Flag U = data correct before manual quality control - Flag O = data correct ' \
                      'after manual quality control, other flags denote incorrect data. ' \
                      'Data processing at ICOS ATC is described in [Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    quality_id = ds.createVariable('quality_id', 'i', ('time',), fill_value=-9,
                                   zlib=True)
    quality_id.long_name = 'quality_id'
    quality_id.comment = 'unique id linking to the QC provenance - Data processing at ICOS ATC is described in ' \
                         '[Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    instrument = ds.createVariable('instrument', 'i', ('time',), fill_value=-9,
                                   zlib=True)
    instrument.long_name = 'instrument_ID_to_detect_atmospheric_parameter'
    instrument.comment = 'Instrument ID used to detect atmospheric parameter. See provider_comment if available.'
    instrument.provider_comment = 'This variable is the ICOS provided Instrument ID'

    icos_datalevel = ds.createVariable('icos_datalevel', 'b', ('time',),
                                       fill_value='255', zlib=True)
    icos_datalevel.long_name = 'icos_data_release_level'
    icos_datalevel.comment = 'Level 0 means pre-ICOS or non-ICOS data (processing by PI); Level 1 means NRT=' \
                             'near real-time data (Automatic Quality Control by ICOS ATC) delay max 24 hrs; Level 2 means final ' \
                             'quality data (Manual and automatic QC by PI and ATC - Data processing at ICOS ATC is described in ' \
                             '[Hazan et al., 2016], doi:10.5194/amt-9-4719-2016.'

    icos_LTR = ds.createVariable('icos_LTR', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    icos_LTR.long_name = 'icos_long_term_repeatability'
    icos_LTR.units = 'mol mol-1'
    icos_LTR.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                       '2015] https://doi.org/10.5194/amt-8-3867-2015'

    icos_CMR = ds.createVariable('icos_SMR', 'f4', ('time',),
                                 fill_value=np.nan, zlib=True)
    icos_CMR.long_name = 'icos_continuous_measurement_repeatability'
    icos_CMR.units = 'mol mol-1'
    icos_CMR.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                       '2015] https://doi.org/10.5194/amt-8-3867-2015'

    icos_STTB = ds.createVariable('icos_STTB', 'f4', ('time',),
                                  fill_value=np.nan, zlib=True)
    icos_STTB.long_name = 'icos_short_term_target_bias'
    icos_STTB.units = 'mol mol-1'
    icos_STTB.comment = 'Analytical uncertainty parameters LTR, SMR and STTB are described in [Yver Kwok et al, ' \
                        '2015] https://doi.org/10.5194/amt-8-3867-2015'

    obs_flag = ds.createVariable('obs_flag', 'b', ('time',), fill_value=1,
                                 zlib=True)
    obs_flag.long_name = 'obs_flag';
    obs_flag.units = 'binary';
    obs_flag.comment = 'Determined by data provider (1: large spatial scale representation; 0: ' \
                       'local/regional influence).  The implementation of this flag is still being developed.'

    obspack_id = ds.createVariable('obspack_id', 'c',
                                   ('time', 'string_of_200chars',), zlib=True)
    obspack_id.long_name = 'obs_flag';
    obspack_id.comment = 'Unique identification string that distinguishes the data item from all other data items ' \
                         'both within an ObsPack product, and across any ObsPack data product. It includes obspack_name, ' \
                         'dataset_name, and obspack_num, with each field delimited by a tilde (~).'

    assimilation_concerns = ds.createVariable('assimilation_concerns', 'b',
                                              ('time', 'dim_concerns'),
                                              zlib=True)
    assimilation_concerns.long_name = 'assimilation_concerns'
    assimilation_concerns.units = 'NA'
    assimilation_concerns.order = 'time window, representivity, variability, under review, wdcgg-background, ' \
                                  'scale_conversion'
    assimilation_concerns.comment = 'Values in this array indicate if the given observation has the assimilation ' \
                                    'concern defined by each column. A value of 0 means that there is no concern or it is not known to exist, ' \
                                    'and a non-zero value means that this concern does exist. Data suitable for a global scale model in ' \
                                    'general will have a 0 in the time window, representivity, and variability columns of this variable. The' \
                                    'implementation of this variable is still being developed.'

    obs_num = ds.createVariable('obs_num', 'i', ('time',), zlib=True)
    obs_num.long_name = 'unique_dataset_observation_number'
    obs_num.comment = 'Unique observation number in this data set.  Range is from 1 to ' + str(
        len(df) + 1)

    obspack_num = ds.createVariable('obspack_num', 'i', ('time',), zlib=True)
    obspack_num.long_name = 'unique_ObsPack_observation_number'
    obspack_num.comment = 'Unique observation index number across all data sets in the ObsPack data product. ' \
                          'Range is from 1 to max_obspack_num'

    # fill the attributes, most value are default and copied from Obspack V7 2021 and some need to be replaced
    # with actual info before writing to netcdf
    obspack_name = 'obspack_' + c.gas + '_' + str(
        lab_id) + '_GV_ICOSFT2025.1_' + dt.datetime.now().strftime('%Y%m%d')

    s = c.icos_stations[c.icos_stations.Hist == station.id]
    lab_id = s.NOAALabNr.values[0]
    lab_name = s.NOAA_Lab_name.values[0]
    TZ = s.Timezone.values[0]
    if s.ICOS_L12.values[0] == '':
        isICOS = 'No'
    else:
        isICOS = 'Yes'
    oscarId = s.OSCAR_ID.values[0]
    if oscarId == '':
        oscarId = 'n.a.'

    # now finally time to start writing the data arrays!
    def rndts(dat, offsetSec: int | float = 0):
        return round(dat.to_pydatetime().timestamp() + offsetSec)

    tim = [rndts(i, 1800.0) for i in df.index]
    time[:] = tim

    timstart = [rndts(i) for i in df.index]
    start_time[:] = timstart

    def toiso(dat, offsetSec=0):
        dat = dat + dt.timedelta(seconds=offsetSec)
        return dat.isoformat() + 'Z'

    isof = [toiso(i, 1800) for i in df.index]
    iso = netCDF4.stringtochar(np.array(isof, dtype='S20'))
    datetime[:] = iso

    def year_frac(dat, offsetSec: int | float = 0):
        dat = dat + dt.timedelta(seconds=offsetSec)
        start = dt.datetime(dat.year, 1, 1, 0, 0, 0)
        endyr = dt.datetime(dat.year + 1, 1, 1, 0, 0, 0)
        yearlen = dt.datetime.timestamp(endyr) - dt.datetime.timestamp(start)
        year_frac = (dt.datetime.timestamp(dat) - dt.datetime.timestamp(
            start)) / yearlen
        return dat.year + year_frac

    timdec = [year_frac(i, 1801.1) for i in df.index]
    time_decimal[:] = timdec

    timeseries_start = df.index[0].isoformat() + 'Z'
    timeseries_end = df.index[len(df) - 1].isoformat() + 'Z'

    def tocomp(dat, OffsetSec: int | float = 0):
        dat = dat + dt.timedelta(seconds=OffsetSec)
        return [dat.year, dat.month, dat.day, dat.hour, dat.minute, 0]

    timcomp = [tocomp(i, 1801.1) for i in df.index]
    time_components[:] = timcomp

    timcomp = [tocomp(i, 1800.0 + TZ * 3600.0) for i in df.index]
    solartime_components[:] = timcomp

    def scaleAndMask(dff, col, fact: int | float = 1):
        dff[col] = dff[col] / fact
        dff.loc[(dff[col] < 0), col] = np.nan
        return dff[col]

    value[:] = scaleAndMask(df, 'Meas', factor)
    value_std_dev[:] = scaleAndMask(df, 'Stdev', factor)
    nvalue[:] = df.NbPoints
    latitude[:] = station.location.lat
    longitude[:] = station.location.lon
    altitude[:] = float(station.location.alt) + hgh
    intake_height[:] = hgh
    qc_flag[:] = df.Flag
    icos_datalevel[:] = df.Level
    try:
        icos_LTR[:] = scaleAndMask(df, 'LTR', factor)
        icos_CMR[:] = scaleAndMask(df, 'CMR', factor)
        icos_STTB[:] = scaleAndMask(df, 'STTB', factor)
    except:
        icos_LTR[:] = np.nan
        icos_CMR[:] = np.nan
        icos_STTB[:] = np.nan
    quality_id[:] = df.QualityId
    try:
        instrument[:] = df.InstrumentId
    except:
        instrument[:] = -1
    obs_flag[:] = 1
    obs_num[:] = np.arange(1, len(df) + 1, 1)
    obspack_num[:] = np.arange(c.cntAll + 1, c.cntAll + len(df) + 1, 1)
    ss = np.array(
        [obspack_name + '~' + f_name + '~' + str(c.cntAll + i + 1) for i in
         range(len(df))], dtype='S200')
    obspack_id[:] = netCDF4.stringtochar(ss)

    assimilation_concerns[:, :] = 0

    if c.gas == 'co2':
        warning = 'In Feb 2021, NOAA updated the WMO CO2 scale from version X2007 to X2019 ' \
                  '(Hall et al., 2021). The X2019 scale supersedes all previous versions of the WMO scale and is ' \
                  'used in this GV+ release. Values contributed on scales other than X2019 have been adjusted by ' \
                  'either known scale offsets or with the known X2019 to X2007 relationship to account for changes ' \
                  'in the scale relationship caused by the X2019 revision.'
    else:
        warning = ''

    attr = {'site_code': station.id,
            'site_name': station.org.name,
            # python quirk. station.name returns the name of the station object
            'site_country': station.countryCode,
            'site_latitude': station.location.lat,
            'site_longitude': station.location.lon,
            'site_elevation': station.location.alt,
            'site_elevation_unit': 'masl',
            'site_position_comment': 'This is the nominal location of the site. The sampling location at many sites' \
                                     ' has changed over time, and we report here the most recent nominal location. The actual sampling location' \
                                     ' for each observation is not necessarily the site location. The sampling locations for each observation' \
                                     ' are reported in the latitude, longitude, and altitude variables..',
            'site_utc2lst': TZ,
            'site_utc2lst_comment': 'Add site_utc2lst hours to convert a time stamp in UTC (Coordinated ' \
                                    'Universal Time) to LST (Local Standard Time).',
            'site_url': station.org.self.uri,
            'site_oscar_id': oscarId,
            'warning_dataset_scale': warning,
            'dataset_creation_date': dt.datetime.now().isoformat(),
            'dataset_num': nc_cnt,
            'dataset_name': f_name,
            'dataset_globalview_prefix': station.id + '_' + str(lab_id) + 'C0',
            'dataset_process': "PassThru",
            'dataset_alternative_names': 'NA',
            'dataset_alternative_names_description': 'The attribute dataset_alternative_names is used to identify ' \
                                                     'all other dataset names that have been used for the record in this dataset. To obtain the full ' \
                                                     'record for this dataset please use all alternatively named datasets that appear in this ObsPack ' \
                                                     'product and the corresponding release of other ObsPacks if applicable.',
            'dataset_alternative_names_comment': '',
            'dataset_parameter': c.gas,
            'dataset_project': 'surface-insitu or tower-insitu',
            'dataset_platform': 'fixed',
            'dataset_map': 'https://meta.icos-cp.eu/station/?station=/resources/stations/AS_' + station.id + '&icon=https://static.icos-cp.eu/share/stations/icons/as.png',
            'dataset_selection': 'all hourly data from ' + str(
                hgh) + ' magl intake',
            'dataset_selection_tag': 'allvalid-' + str(hgh) + 'magl',
            'dataset_comment': 'Please note that some datasets included in past Obspack releases are now ' \
                               'provided by the ICOS program. The valid data selection scheme for ICOS datasets may differ ' \
                               'significantly from the selection scheme provided previously by contributing laboratories.)',
            'dataset_contains_ICOS_L1_and_or_L2_data': isICOS,
            'dataset_calibration_scale': calib_scale,
            'dataset_start_date': timeseries_start,
            'dataset_stop_date': timeseries_end,
            'dataset_data_frequency': 1.,
            'dataset_data_frequency_unit': 'hour',
            'dataset_time_window_lst': '0-23',
            'dataset_time_window_utc': '0-23',
            'dataset_time_window_exclusion': 'F',
            'dataset_intake_ht': str(hgh),
            'dataset_intake_ht_unit': 'magl',
            'dataset_description': 'This data package is intended for use in carbon cycle inverse modeling, model ' \
                                   'evaluation, and satellite validation studies.  Please report errors and send comments regarding ' \
                                   'this product to the ObsPack originators. Please read carefully the ObsPack Fair Use statement ' \
                                   'and cite appropriately. DOI metadata for this product are available ' \
                                   'at https://search.datacite.org/works/10.18160/' + doi_cite + '.',
            'dataset_usage_url': 'https://doi.org/10.18160/' + doi_cite,
            'dataset_usage_description': 'In addition to this product\'s citation we ask that you please cite ' \
                                         'the following provider citations when using data from this dataset.',
            'dataset_provider_citation_total': str(len(citations))}

    for i in range(0, len(citations)):
        attr.update({'dataset_provider_citation_' + str(i + 1): citations[i]})

    attr2 = {
        'dataset_provider_license': 'DATA POLICY: ICOS DATA is licensed under a Creative Commons Attribution ' \
                                    '4.0 international licence (http://creativecommons.org/licenses/by/4.0/.The ICOS data licence is ' \
                                    'described at https://data.icos-cp.eu/licence.',
        'dataset_provider_license_url': 'http://creativecommons.org/licenses/by/4.0/',
        'dataset_reference_total_listed': 0,
        'dataset_contribution': 'These data are provided by ICOS-RI AND ' + lab_name + ' AND ICOS ATC, CAL, Carbon Portal. ' \
                                                                                      'Principal investigators and contributors include ' + persons + '.',
        'obspack_variables_and_attributes': 'ObsPack variables and attributes are described at ' \
                                            'www.gml.noaa.gov/ccgg/obspack/documentation.html#MetaData',
        'obspack_name': obspack_name,
        'obspack_description': 'This data file is part of a data package called Obspack that is intended ' \
                               'for use in carbon cycle inverse modeling, model ' \
                               'evaluation, and satellite validation studies.  Please report errors and send comments regarding this ' \
                               'product to the ObsPack originators. Please read carefully the ObsPack Fair Use statement and cite ' \
                               'appropriately. DOI metadata for this product are available at ' \
                               'https://search.datacite.org/works/10.18160/' + doi_cite + \
                               'Please visit http://www.gml.noaa.gov/ccgg/obspack/ for more information.',
        'obspack_creation_date': dt.datetime.now().isoformat(),
        'obspack_warning': 'Every effort is made to create the most accurate and precise data product possible.' \
                           ' Contributors reserve the right to make corrections to this product and data based on recalibration of ' \
                           'standard gases or for other reasons deemed scientifically justified. Contributors to this product are ' \
                           'not responsible for results and conclusions based on use of this product without regard to this warning.',
        'obspack_fair_use': 'This cooperative data product is made freely available to the scientific community ' \
                            'and is intended to stimulate and support carbon cycle modeling studies.  We rely on the ethics and ' \
                            'integrity of the user to assure that each contributing national and university laboratory receives ' \
                            'fair credit for their work. Fair credit will depend on the nature of the work and the requirements of ' \
                            'the institutions involved.Your use of this data product implies an agreement to contact each ' \
                            'contributing laboratory for data sets used to discuss the nature of the work and the appropriate level' \
                            'of acknowledgement. If this product is essential to the work, or if an important result or conclusion ' \
                            'depends on this product, co-authorship may be appropriate. This should be discussed with the ' \
                            'appropriate data providers at an early stage in the work.  Contacting the data providers is not ' \
                            'optional; if you use this data product, you must contact the applicable data providers. To help you ' \
                            'meet your obligation, the data product includes an e-mail distribution list of all data providers. ' \
                            'This data product must be obtained directly from the ICOS Data Portal at ' \
                            'https://data.icos-cp.eu/portal/ and we ask you to not re-distribute. In addition to the conditions of ' \
                            'fair use as stated above, users are requested to include the ObsPack product citation in any publication or ' \
                            'presentation using the product.  The required citation is included in every data product.',
        'obspack_usage_policy': 'https://www.icos-cp.eu/data-services/about-data-portal/data-license',
        'obspack_data_license': 'https://creativecommons.org/licenses/by/4.0/',
        'obspack_identifier_link': settings['doi_collection'],
        'obspack_citation': doi_citation('https://doi.org/10.18160/' + doi_cite),
        'Conventions': 'CF-1.7',
        'nc.institution': 'Unidata',
        'source': 'ICOS RI',
        'history': str(
            dt.datetime.utcnow()) + ' Python in Jupyter notebook createObspackv34.ipynb'
    }
    attr.update(attr2)
    ds.setncatts(attr)

    #    except:
    #        print('Error in writing netcdf ',f_name)
    #        ds.close()
    #        raise
    #    finally:
    ds.sync()
    ds.close()

    if c.do_txt:
        csv_data = pd.DataFrame()
        csv_data['datetimeISO'] = isof
        csv_data['year'] = [dt.datetime.utcfromtimestamp(i).year for i in tim]
        csv_data['month'] = [dt.datetime.utcfromtimestamp(i).month for i in tim]
        csv_data['day'] = [dt.datetime.utcfromtimestamp(i).day for i in tim]
        csv_data['hour'] = [dt.datetime.utcfromtimestamp(i).hour for i in tim]
        csv_data['minute'] = [dt.datetime.utcfromtimestamp(i).minute for i in tim]
        csv_data['second'] = [dt.datetime.utcfromtimestamp(i).second for i in tim]
        csv_data['time'] = tim
        csv_data['time_decimal'] = timdec
        csv_data['value'] = scaleAndMask(df, 'Meas', 1 / factor).values
        csv_data['value_std_dev'] = scaleAndMask(df, 'Stdev', 1 / factor).values
        csv_data['nvalue'] = df.NbPoints.values
        csv_data['qc_flag'] = df.Flag.values
        csv_data['icos_datalevel'] = df.Level.values
        try:
            csv_data['icos_LTR'] = scaleAndMask(df, 'LTR', 1 / factor).values
            csv_data['icos_CMR'] = scaleAndMask(df, 'CMR', 1 / factor).values
            csv_data['icos_STTB'] = scaleAndMask(df, 'STTB', 1 / factor).values
        except (
                KeyError, AttributeError, TypeError, ValueError, ZeroDivisionError, NameError
        ) as column_exception:
            csv_data['icos_LTR'] = np.nan
            csv_data['icos_CMR'] = np.nan
            csv_data['icos_STTB'] = np.nan
        csv_data['latitude'] = station.location.lat
        csv_data['longitude'] = station.location.lon
        csv_data['altitude'] = float(station.location.alt) + hgh
        csv_data['intake_height'] = hgh
        csv_data['unique_sample_location_num'] = np.arange(1, len(df) + 1, 1)
        csv_data['obspack_num'] = np.arange(c.cntAll + 1, c.cntAll + len(df) + 1, 1)
        csv_data['obspack_id'] = [
            obspack_name + '~' + f_name + '~' + str(c.cntAll + i + 1) for i in
            range(len(df))]

        csv_path = Path(c.txt, f'{f_name}.txt')
        csv_data.to_csv(csv_path, sep=' ', na_rep='-999999', header=True, index=False, float_format='%.5f')
        header = create_txt_header(obs_name=obspack_name, nc_file=nc_name, doi_cite=doi_cite, config=c)

        with open(csv_path, 'r') as file_handle:
            csv = file_handle.readlines()
        with open(csv_path, 'w') as file_handle:
            for i in header:
                file_handle.write(i + '\n')
            for i in csv:
                file_handle.write(i)
        # print('Done saving ', csv_path)

    c.cntAll = c.cntAll + len(df)

    spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackTimeSerieResult'
    if c.gas == 'ch4':
        spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackCH4TimeSeriesResult'
    if c.gas == 'n2o':
        spec_url = 'http://meta.icos-cp.eu/resources/cpmeta/ObspackN2oTimeSeriesResult'

    res = generate_meta(config=c, f_name=nc_name, obj_spec=spec_url, input_doi=f'10.18160/{doi_cite}', scale=calib_scale)
    pretty = json.dumps(res, indent=2)
    json_f_name = Path(c.json, f'{nc_name.stem}.json')
    with open(json_f_name, 'w') as f:
        f.write(pretty)
    # print('Done saving ', json_f_name)


def create_txt_header(
        config: Config,
        obs_name: str,
        nc_file: Path,
        doi_cite: str,
        cit: str = ''
) -> list:

    head = []
    with open(config.header) as f:
        pre = f.readlines()
    stream = os.popen('ncdump -h ' + str(nc_file.resolve()))
    output = stream.readlines()
    filtered = []
    variables = ['#', '# ------------------------------------------------------------->>>>',
                 '# VARIABLE ATTRIBUTES', '#']
    for i in output:
        if '\t\t' in i:
            i = i.replace(' ;\n', '')
            i = i.replace('"', '')
            if '\t\t:' in i:
                i = i.replace('\t\t:', '# ')
                filtered.append(i)
            else:
                i = i.replace('\t\t', '# ')
                variables.append(i)
    variables.append('#')
    variables.append('# VARIABLE ORDER')
    variables.append('#')
    h_len = len(filtered) + len(variables) + len(pre) + 1

    fname = os.path.basename(nc_file)
    (dataset, sep, ext) = fname.rpartition('.')
    head.append('# header_lines : ' + str(h_len))
    if cit == '':
        cit = doi_citation(doi_id=f'10.18160/{doi_cite}')
    for i in pre:
        i = i.replace('\n', '')
        if 'doi_xxx' in i:
            i = i.replace('doi_xxx', doi_cite)
        if 'citation_xxx' in i:
            i = i.replace('citation_xxx', cit)
        if 'obspack_xxx' in i:
            i = i.replace('obspack_xxx', obs_name)
        if 'dataset_xxx' in i:
            i = i.replace('dataset_xxx', dataset)
        head.append(i)
    for i in filtered:
        head.append(i)
    for i in variables:
        head.append(i)
    return head


def generate_meta(
        config: Config,
        f_name: Path,
        obj_spec: str,
        input_doi: str,
        scale: str
) -> dict[str, Any]:
    """Generate and upload metadata."""
    f_name_str = str(f_name.resolve())
    xarray_ds = xr.open_dataset(f_name)
    try:
        variable = [variable for variable in ['co2_', 'ch4_', 'co_', 'n2o_'] if variable in f_name_str]
        if len(variable) != 1:
            exit(f'\tError! Incorrect number of variables detected: {variable} file: {f_name_str}.\n'
                 f'\tNeed to have only one variable specified in file\'s name.\n'
                 f'\tExiting...')
        variable = variable[0][0:-1]

        json_package = {
            "submitterId": "CP",
            "hashSum": get_hash_sum(path=f_name),
            "fileName": f_name.name,
            "specificInfo": {
                "station": xarray_ds.site_url,
                "samplingHeight": xarray_ds.intake_height[0].item(),
                "production": {
                    "creator": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "contributors": config.file_contribs.uri.to_list(),
                    "hostOrganization": "http://meta.icos-cp.eu/resources/organizations/CP",
                    "comment": "European Obspack observational timeseries in netcdf format of ambient mole "
                               f"fraction of {variable} in dry air calibrated using the WMO GAW calibration "
                               f"scale {scale}, composed of (all whenever available) historical PI QCed "
                               f"data, ICOS Level 2 data and ICOS NRT data",
                    "creationDate": xarray_ds.dataset_creation_date+"Z",
                    "sources": config.d_files
                }
            },
            "objectSpecification": obj_spec,
            "isNextVersionOf": [get_prev_by_name(anchor=f_name.name)],
            "preExistingDoi": input_doi.replace('https://doi.org/', ''),
            "references": {
                "autodeprecateSameFilenameObjects": True,
                "keywords": [scale, "atmospheric dry air "+variable+" mole fraction"]
            }
        }
    finally:
        xarray_ds.close()
    return json_package
