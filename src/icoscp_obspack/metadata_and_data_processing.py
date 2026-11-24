# Standard library imports.
import pickle
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

# Related third party imports.
import numpy as np
import pandas as pd
from icoscp_core.icos import ATMO_STATION, data, meta
from icoscp_core.metaclient import Station
from icoscp_core.metacore import AtcStationSpecifics, DataObject, Person
from icoscp_core.queries.stationlist import StationLite
from icoscp_core.rolemeta import Membership
from pandas._typing import DtypeArg

# Local application/library specific imports.
from icoscp_obspack.citation import Author, AuthorWithWeight, citation, doi_citation
from icoscp_obspack.config import Config, create_obspack_release_name
from icoscp_obspack.data_writer import (
    INT_FILL_VALUE,
    DataWriter,
    NetcdfFileInfoForUploader,
    StationExtraInfo,
)
from icoscp_obspack.doi import GeoLocation, GeoLocationPoint, produce_doi_meta
from icoscp_obspack.geo_json import (
    GeoFeature,
    GeoJson,
    Geometry,
    GeoProperties,
    save_geo_json,
    save_geo_json_pickle,
)
from icoscp_obspack.plotting import get_global_average, ghg_filter_ts, plot_timeseries_station
from icoscp_obspack.tracers import (
    DATA_LEVEL_PER_TYPE,
    FASTTRACK_SPEC,
    GOOD_FLAGS_PER_TYPE,
    SENTINEL_VALUE_FLAG,
    Tracer,
)
from icoscp_obspack.utils import timeit

# Everything specific to a tracer comes from its descriptor (see tracers.py). Adding support for
# a tracer is done by adding a descriptor there; nothing in this module branches on the tracer's
# identity.

# Maximum number of data objects that can be found for a given station and gas species.
# This limit is not expected to be reached anytime soon at any station, so it is not included
# in the configuration file.
n_max_dobj = 200

# Additional stations that are not included in ATMO_STATION yet but for which
# some data has been released by ATC.
additional_stations: list[StationLite] = [
    StationLite(
        uri='http://meta.icos-cp.eu/resources/stations/AS_INE',
        label='Ineia (INE)', comments=[], id='INE', name='Ineia',
        type_uri='http://meta.icos-cp.eu/ontologies/cpmeta/AS',
        country_code='CY', lat=34.9621, lon=32.3777, elevation=660.0, geo_json=None
    ),
    StationLite(
        uri='http://meta.icos-cp.eu/resources/stations/AS_VTI',
        label='Valentia Island (VTI)', comments=[], id='VTI', name='Valentia Island',
        type_uri='http://meta.icos-cp.eu/ontologies/cpmeta/AS',
        country_code='IE', lat=51.908, lon=-10.4032, elevation=25.0, geo_json=None
    )
]

# Additional authors for specific stations.
additional_authors: dict[str, list[Author]] = {
    'HFD': [
        Author(
            uri='http://meta.icos-cp.eu/resources/people/Chris_Rennick',
            first_name='Chris',
            last_name='Rennick',
            orcid='0000-0003-4993-0156',
            weight=100,
            start=None,
            end=None
        )]
}

# Gases to skip for some station (to be revised before each ObsPack release).
gases_to_skip: dict[str, list[str]] = {
    'HEL': ['co'], 'HUN': ['n2o'], 'IPR': ['n2o'], 'PAL': ['n2o'], 'UTO': ['n2o'], 'WES': ['co']}

# Sampling heights to skip for some stations (to be revised before each ObsPack release).
sampling_heights_to_skip: dict[str, list[float]] = {'BIR': [2.5], 'HUN': [96], 'INE': [3], 'JFJ': [5]}

# Data objects that are deprecated but should be included for some stations and sampling heights
# (to be revised before each ObsPack release).
deprecated_dobjs_to_use: dict[str, dict[str, dict[float, list[str]]]] = {
    'co2': {},
    'ch4': {},
    'n2o': {},
    'co': {},
    'rn': {},
    '14co2': {}
}
#replace_sampling_height: dict[str, dict[float, float]] = {
#    'HUN': {48: 50}
#}

@dataclass(frozen=True)
class SamplingHeightContent:
    data: pd.DataFrame
    station_meta: Station
    authors: list[AuthorWithWeight]
    citations: list[str]
    hashsums: list[str]

@dataclass(frozen=True)
class LoadedDataset:
    """The content of a single data object, tagged with the ICOS data type it belongs to."""
    dobj: DataObject
    data_type: str
    data: pd.DataFrame

def main():
    # The gas is validated by Config, which also resolves the application's paths.
    c = Config()
    c.create_output_directories()
    print(
        f'Running ObsPack application for gas "{c.gas}"...'
        f'\nObsPack product name: {create_obspack_release_name(c)}'
        f'\nTitle for DOI: {c.title_for_doi}'
        f'\nDescription for DOI: {c.description_for_doi}'
        f'\n\n{"_"*122}\nProcessing metadata and data...')
    collecting_info_start_time = datetime.now(tz=timezone.utc)
    content_from_all_sampling_heights: dict[str, dict[float, SamplingHeightContent]] = {}
    collection_authors: list[Author] = []
    geo_locations: list[GeoLocation] = []
    geo_features: list[GeoFeature] = []
    earliest_dt: datetime | None = None
    latest_dt: datetime | None = None
    meta_stations = meta.list_stations(ATMO_STATION)
    meta_stations.extend(additional_stations)
    n_stations = len(meta_stations)
    for n, station in enumerate(meta_stations):
        print(f'\n\n{"-"*122}\nStation {station.id} ({n+1}/{n_stations})\n{"-"*122}')
        if station.id in gases_to_skip.keys() and c.gas in gases_to_skip[station.id]:
            print(f'Skipping station {station.id} (see dict `gases_to_skip`).')
            continue
        fetching_station_info_start_time = datetime.now(tz=timezone.utc)
        station_meta = meta.get_station_meta(station.uri)
        # Filter out stations that are not ATC stations or ICOS stations of level 1 or 2.
        if not isinstance(station_meta.specificInfo, AtcStationSpecifics):
            print(f'Skipping station {station.id} because it is not an ATC station.')
            continue
        if station_meta.specificInfo.stationClass not in ['1', '2'] and c.use_only_icos_stations_l1_or_l2:
            print(f'Skipping station {station.id} because it is not a ICOS level 1 or 2 station.')
            continue
        # Collect information about the staff of the station.
        station_authors: list[Author] = [
            author_from_membership(membership) for membership in station_meta.staff]
        if station.id in additional_authors.keys():
            station_authors.extend(additional_authors[station.id])
        persons_at_station: list[Person] = [member.person for member in station_meta.staff]
        fetching_station_info_end_time = timeit(fetching_station_info_start_time, f'Collect metadata and authors for station {station.id}', c.print_timing_messages)

        # Find all relevant data objects for a given station and separate them by sampling height.
        dobjs_per_sampling_height = dobjs_from_station_by_sampling_height(station, c.tracer)
        if len(dobjs_per_sampling_height) == 0:
            continue
        _ = timeit(fetching_station_info_end_time, f'Find data objects for station {station.id} and organize them by sampling height', c.print_timing_messages)

        # Store geolocation of station for DOI minting and Obspack release upload.
        geo_locations.append(GeoLocation(
            GeoLocationPoint(pointLongitude=station.lon, pointLatitude=station.lat),
            geoLocationPlace=station.id))
        if station.lon is not None and station.lat is not None:
            geo_features.append(GeoFeature(
                geometry=Geometry(coordinates=(station.lon, station.lat), type="Point"),
                properties=GeoProperties(label=station.id),
                type="Feature"))

        if c.print_timing_messages:
            print('-'*122)

        # Process metadata and data for each sampling height at the current station.
        for sampling_height, dobjs_at_sampling_height in dobjs_per_sampling_height.items():
            if station.id in sampling_heights_to_skip.keys() \
                and sampling_height in sampling_heights_to_skip[station.id]:
                continue
            if station_meta.specificInfo.stationClass is None:
                station_class_msg = 'non-ICOS station'
            else:
                station_class_msg = f'class {station_meta.specificInfo.stationClass}'
            print(
                f'Station {station.id} ({station_class_msg}),'
                f' Sampling height: {sampling_height} m,'
                f' Processing {len(dobjs_at_sampling_height)} file(s)')

            fetching_sampling_height_start_time = datetime.now(tz=timezone.utc)
            # Read the data files, then produce one dataset (pandas.DataFrame) with all datasets
            # from the current station and sampling height.
            loaded_datasets = load_datasets(
                dobjs_at_sampling_height, c.tracer, c.useflags, c.zip, c.use_cached_datafiles)
            data_at_sampling_height, used_dobjs_at_sampling_height = combine_datasets(
                loaded_datasets, station.id, sampling_height, c.tracer)
            if data_at_sampling_height.empty:
                print(f'No data found for station {station.id} and sampling height {sampling_height} m.')
                continue
            combining_datasets_end_time = timeit(fetching_sampling_height_start_time, f'Combine data files for station {station.id} and sampling height {sampling_height}', c.print_timing_messages)

            # Track the earliest and latest measurement date and time of the entire Obspack product.
            # The values are used for the upper limit of the x-axis of the figures, and when uploading
            # the Obspack release to the data portal.
            if earliest_dt is None or data_at_sampling_height.index[0] < earliest_dt:
                earliest_dt = data_at_sampling_height.index[0]
            if latest_dt is None or data_at_sampling_height.index[-1] > latest_dt:
                latest_dt = data_at_sampling_height.index[-1]

            # Handle authors and citations.
            if station_meta.specificInfo.stationClass is None:
                citations: list[str] = []
            else:
                citations: list[str] = c.default_citations.copy()
            file_authors: list[Author] = station_authors.copy()
            short_hashsums: list[str] = []
            for dobj in used_dobjs_at_sampling_height:
                path_to_pkl_file = Path(c.pickle, f'{dobj.hash}.pkl')
                if c.debug and not c.refresh_pickles:
                    with open(path_to_pkl_file, 'rb') as pkl_file:
                        file_authors: list[Author] = pickle.load(pkl_file)
                else:
                    persons: list[Person] = []
                    if dobj.references.authors is not None:
                        persons = [
                            author for author in dobj.references.authors
                            if isinstance(author, Person) and author not in persons_at_station]
                    dobj_authors: list[Author] = [
                        author_from_person(person) for person in persons]
                    file_authors.extend(dobj_authors)
                if c.debug and c.refresh_pickles:
                    with open(path_to_pkl_file, 'wb') as pkl_file:
                        pickle.dump(file_authors, pkl_file)
                if dobj.references.citationString is not None:
                    citations.append(dobj.references.citationString)
                short_hashsums.append(dobj.hash[:24])
            file_authors_cleaned = clean_and_sort_authors(file_authors, c.default_author_weight)
            collection_authors.extend(file_authors)
            _ = timeit(combining_datasets_end_time, f'Handle authors and citations for station {station.id} and sampling height {sampling_height}', c.print_timing_messages)

            content_from_all_sampling_heights.setdefault(station.id, {})[sampling_height] = SamplingHeightContent(
                data=data_at_sampling_height,
                station_meta=station_meta,
                authors=file_authors_cleaned,
                citations=citations,
                hashsums=short_hashsums)

            _ = timeit(fetching_sampling_height_start_time, f'Total processing time for station {station.id} and sampling height {sampling_height}', c.print_timing_messages)
            if c.print_timing_messages:
                print('-'*122)
        _ = timeit(fetching_station_info_start_time, f'Total processing time for station {station.id}', c.print_timing_messages)
        if c.print_timing_messages:
            print('-'*122)
    if c.print_timing_messages:
        print(f'\n\n{"-"*122}')
    _ = timeit(collecting_info_start_time, 'Total time to process metadata and data.', c.print_timing_messages)
    n_stations_with_data = len(content_from_all_sampling_heights)
    n_sampling_heights_with_data = sum([len(sh) for sh in content_from_all_sampling_heights.values()])
    print(
        f'\n\n{"-"*122}\nFinished processing metadata and data from {n_stations_with_data} stations and'
        f' {n_sampling_heights_with_data} sampling heights where data exist.\nThe earliest measurement'
        f' was taken on {earliest_dt} and the latest measurement was taken on {latest_dt}.\n{"-"*122}')

    # Fetch content from some files.
    #lab_numbers: pd.DataFrame = pd.read_csv(c.file_lab_numbers, comment='#', delimiter=';')
    icos_stations: pd.DataFrame = pd.read_csv(c.file_icos_stations, comment='#', delimiter=';')
    if c.do_png:
        global_avg: pd.DataFrame = get_global_average(c)
        if global_avg.empty:
            global_avg_filtered = pd.DataFrame(columns=['Trend'])
        else:
            global_avg_filtered: pd.DataFrame = \
                ghg_filter_ts(global_avg['JulDate'], global_avg['Meas']) if c.analyse else pd.DataFrame()
    else:
        global_avg = pd.DataFrame()
        global_avg_filtered = pd.DataFrame()

    # Handle authors to the Obspack collection.
    collection_authors_cleaned = clean_and_sort_authors(collection_authors, c.default_author_weight)
    with open(Path(c.output, f'authors_{c.gas}.pkl'), 'wb') as authors_file:
        pickle.dump(collection_authors_cleaned, authors_file)
    # Save JSON to be pasted in the DOI app for minting the DOI of the Obspack release.
    produce_doi_meta(c, collection_authors_cleaned, geo_locations)
    # Save contributor and creator info as json for the DOI minting.
    # These files are not needed anymore since the JSON created in the previous step includes
    # all information about creators and contributors, but it is kept here as legacy.
    path_to_creators_file = Path(c.output, f'creators_{c.gas}.json')
    path_to_contributors_file = Path(c.output, f'contributors_{c.gas}.json')
    with open(path_to_creators_file, 'w') as creators_file:
        creators_file.write(citation(collection_authors_cleaned, as_contrib=False))
    with open(path_to_contributors_file, 'w') as contributors_file:
        contributors_file.write(citation(collection_authors_cleaned, as_contrib=True))
    # Save GeoJSON of station locations. The GeoJSON can be used when uploading the Obspack release
    # to the data portal.
    geo_json = GeoJson(features=geo_features, type='FeatureCollection')
    save_geo_json(geo_json, Path(c.output, f'GeoJSON_{c.gas}.json'))
    save_geo_json_pickle(geo_json, Path(c.output, f'GeoJSON_{c.gas}.pkl'))
    # Wait for the DOI to be minted before continuing
    user_input = None
    while user_input is None:
        user_input = input(
            f'\n\n{"_"*122}\nThe JSON for the DOI minting is available in {c.doi_json_file}.'
            '\nPress Enter to continue after the new DOI has been minted.')

    # Produce netCDF and CSV files, as well as figures.
    print(f'\n\n{"_"*122}\nWriting data...')
    writing_data_start_time = datetime.now(tz=timezone.utc)
    n_stations = len(content_from_all_sampling_heights)
    station_counter = 0
    row_counter = 0
    nc_files_info_for_uploader: list[NetcdfFileInfoForUploader] = []
    dataset_id = c.tracer.first_dataset_id
    obspack_name = create_obspack_release_name(c, writing_data_start_time)
    obspack_citation = doi_citation(c.doi)
    for station_id, station_content in content_from_all_sampling_heights.items():
        print(f'\n\n{"-"*122}\nStation {station_id} ({station_counter+1}/{n_stations})\n{"-"*122}')
        writing_station_data_start_time = datetime.now(tz=timezone.utc)
        n_heights = len(station_content.keys())
        station_extra_info = extract_station_extra_info(icos_stations, station_id, c.file_icos_stations)
        for sampling_height, sampling_height_content in station_content.items():
            writing_sampling_height_data_start_time = datetime.now(tz=timezone.utc)
            # If a station has more than one measurement height, it is considered a "tower-insitu".
            # If a station has one measurement height, it is considered a "surface-insitu".
            if n_heights > 1:
                filename = '_'.join([
                    c.gas, station_id.lower(), 'tower-insitu', str(station_extra_info.lab_id),
                    f'{int(sampling_height)}magl'])
            else:
                filename = '_'.join([
                    c.gas, station_id.lower(), 'surface-insitu', str(station_extra_info.lab_id),
                    f'{int(sampling_height)}magl'])

            if c.do_png:
                plot_timeseries_station(
                    config=c, dataset=sampling_height_content.data, global_avg=global_avg,
                    global_avg_filtered=global_avg_filtered, station_id=station_id,
                    sampling_height=sampling_height, filename=filename,
                    latest_measurement_dt=latest_dt)
            plotting_end_time = timeit(writing_sampling_height_data_start_time, f'Make figure for station {station_id} and sampling height {sampling_height}', c.print_timing_messages)

            try:
                data_writer = DataWriter(
                    config=c, filename=filename, data=sampling_height_content.data,
                    station=sampling_height_content.station_meta, station_extra_info=station_extra_info,
                    height=sampling_height, authors=sampling_height_content.authors,
                    citations=sampling_height_content.citations, nc_cnt=dataset_id, row_counter=row_counter,
                    hashsums=sampling_height_content.hashsums,
                    dataset_creation_data=datetime.now(tz=timezone.utc),
                    obspack_creation_date=writing_data_start_time.isoformat(),
                    obspack_name=obspack_name, obspack_citation=obspack_citation)
                data_writer.produce_files()
                row_counter += sampling_height_content.data.shape[0]
            except Exception:
                print(f'Error writing NetCDF file "{filename}.')
                raise
            _ = timeit(plotting_end_time, f'Produce netCDF and CSV files for station {station_id} and sampling height {sampling_height}', c.print_timing_messages)

            nc_files_info_for_uploader.append(NetcdfFileInfoForUploader(
                filename=filename,
                folder=c.nc,
                station=station_id,
                sampling_height=sampling_height,
                hash=sampling_height_content.hashsums,
                handle=''))
            dataset_id += 1
            _ = timeit(writing_sampling_height_data_start_time, f'Total processing time for station {station_id} and sampling height {sampling_height}', c.print_timing_messages)
            if c.print_timing_messages:
                print('-'*122)
        station_counter += 1
        _ = timeit(writing_station_data_start_time, f'Total processing time for station {station_id}', c.print_timing_messages)
        if c.print_timing_messages:
            print('-'*122)
    if c.print_timing_messages:
        print(f'\n\n{"-"*122}')
    _ = timeit(writing_data_start_time, 'Total time to producte netCDF and CSV files, as well as figures.', c.print_timing_messages)

    pd.DataFrame(nc_files_info_for_uploader).to_csv(c.info_about_produced_files)

def extract_station_extra_info(
        icos_stations: pd.DataFrame, station_id: str, icos_stations_file: Path) -> StationExtraInfo:
    cond = icos_stations['Hist'] == station_id
    if sum(cond) == 0:
        print(
            f'No information about station {station_id} is available in the file at'
            f' {icos_stations_file}.')
        tz = _prompt_for_timezone(station_id)
        station_extra_info = StationExtraInfo(
            icos_id=station_id, icos_labeled='No', oscar_id='n.a.', lab_id=-1, lab_name='', timezone=tz)
    else:
        station_info = icos_stations.loc[cond].iloc[0]
        icos_labeled = 'No' if station_info['ICOS_L12'] == '' else 'Yes'
        oscar_id = 'n.a.' if station_info['OSCAR_ID'] == '' else station_info['OSCAR_ID']
        # Prompt for time zone if it is not provided in the file.
        try:
            tz = float(station_info['Timezone'])
        except ValueError:
            print(
                f'Time zone for station {station_id} is not provided in the file at'
                f' {icos_stations_file}.')
            tz = _prompt_for_timezone(station_id)
        station_extra_info = StationExtraInfo(
            icos_id=station_id,
            icos_labeled=icos_labeled,
            oscar_id=oscar_id,
            lab_id=int(station_info['NOAALabNr']),
            lab_name=station_info['NOAA_Lab_name'],
            timezone=tz
        )
    if sum(cond) > 1:
        print(
            f'Station {station_id} appears more than once in the file at {icos_stations_file}. '
            'The first occurence is used.')
    return station_extra_info

def dobjs_from_station_by_sampling_height(
        station: StationLite, tracer: Tracer) -> dict[float, list[DataObject]]:
    dobjs_per_sampling_height: dict[float, list[DataObject]] = {}
    specs = list(tracer.specs.values())
    dobjs_lite = meta.list_data_objects(datatype=specs, station=station, limit=n_max_dobj)
    if len(dobjs_lite) == n_max_dobj:
        print(
            f'There might be some unprocessed data objects at station {station.uri} because'
            f' the limit ({n_max_dobj}) has been reached.\nPlease consider rerunning the script'
            ' after setting a higher limit.')
    for dobj_lite in dobjs_lite:
        if dobj_lite.sampling_height is None:
            print(
                f'Skipping data object {dobj_lite.uri} at station {station.uri} because sampling '
                ' height is missing.')
            continue
        # Several tracers share one FastTrack specification, which therefore does not say which
        # tracer a given object is about; its file name does. Tracers with a FastTrack
        # specification of their own, or none at all, need no such disambiguation.
        elif (
            tracer.specs.get('fasttrack') == FASTTRACK_SPEC
            and dobj_lite.datatype_uri == FASTTRACK_SPEC
            and dobj_lite.filename.split('.')[-2].split('_')[-1].lower() != tracer.key):
            continue
        else:
            sampling_height = dobj_lite.sampling_height
            #if (station.id in replace_sampling_height.keys()
            #    and sampling_height in replace_sampling_height[station.id].keys()):
            #    sampling_height = replace_sampling_height[station.id][sampling_height]
            dobjs_per_sampling_height\
                .setdefault(sampling_height, [])\
                .append(meta.get_dobj_meta(dobj_lite))
    # Add deprecated data objects for some stations and sampling heights.
    deprecated_dobjs_at_station = deprecated_dobjs_to_use.get(tracer.key, {}).get(station.id, {})
    for h, urls in deprecated_dobjs_at_station.items():
        dobjs_per_sampling_height.setdefault(h, []).extend([meta.get_dobj_meta(url) for url in urls])
    return dobjs_per_sampling_height

def author_from_membership(membership: Membership) -> Author:
    return Author(
        uri=membership.person.self.uri,
        first_name=membership.person.firstName,
        last_name=membership.person.lastName,
        orcid=membership.person.orcid,
        weight=membership.role.weight,
        start=membership.role.start,
        end=membership.role.end
    )

def author_from_person(person: Person) -> Author:
    return Author(
        uri=person.self.uri,
        first_name=person.firstName,
        last_name=person.lastName,
        orcid=person.orcid,
        weight=None,
        start=None,
        end=None
    )

def clean_and_sort_authors(authors: list[Author], default_weight: int) -> list[AuthorWithWeight]:
    """
    Clean and sort a list of authors.
    :param `authors`:
        A list of `Author`s.
    :param `default_weight`:
        Citation weight to assign to authors whose weight is not set in the metadata.
    :return:
        A sorted list of `Author`s.
    """
    authors_cleaned: list[AuthorWithWeight] = []
    author_per_uri: dict[str, list[Author]] = {}
    for author in set(authors):
        author_per_uri.setdefault(author.uri, []).append(author)
    for authors_with_same_uri in author_per_uri.values():
        weights = [author.weight for author in authors_with_same_uri if author.weight is not None]
        max_weight = max(weights) if weights else None
        # If there is only one instance of the author with this URI, keep it.
        if len(authors_with_same_uri) == 1:
            authors_cleaned.append(AuthorWithWeight.from_author(
                authors_with_same_uri[0], default_weight))
            continue
        # If there are multiple instances of the author with this URI, keep the one with the latest
        # start date among those who have no end date (which indicates that it is the current information).
        # Use the maximum weight of all instances of the author (if available).
        current_authors = [
            author for author in authors_with_same_uri
            if author.start is not None and author.end is None]
        if len(current_authors) > 0:
            current_authors.sort(key=lambda author: author.start or '', reverse=True)
            authors_cleaned.append(AuthorWithWeight.from_author(
                current_authors[0], default_weight, imposed_weight=max_weight))
            continue
        # If there is no current instance of the author, keep the one with the latest end date.
        # Use the maximum weight of all instances of the author (if available).
        authors_with_end_date = [
            author for author in authors_with_same_uri if author.end is not None]
        if len(authors_with_end_date) > 0:
            authors_with_end_date.sort(key=lambda author: author.end or '', reverse=True)
            authors_cleaned.append(AuthorWithWeight.from_author(
                authors_with_end_date[0], default_weight, imposed_weight=max_weight))
            continue
        # If none of the instances of the author has an end date, keep the one with the highest weight.
        # If none of the instances has a weight, assign the default weight.
        authors_with_same_uri.sort(key=lambda author: author.weight or 0, reverse=True)
        authors_cleaned.append(AuthorWithWeight.from_author(
            authors_with_same_uri[0], default_weight))
    authors_cleaned.sort(
        key=lambda author: (-author.weight, author.last_name, author.first_name))
    return authors_cleaned

def load_datasets(
        dobjs: list[DataObject], tracer: Tracer, use_flags: bool, zip_dir: Path,
        use_cached_datafiles: bool) -> list[LoadedDataset]:
    """
    Read and normalize the content of every data object that holds data about `tracer`.
    This is the only part of the combination that reads files or accesses the network, so that
    `combine_datasets` can work purely on the result.
    :param `dobjs`:
        A list of `DataObject` that are related to a station and sampling height.
    :param `tracer`:
        The tracer being processed. Its `value_column` and `std_column` name the columns holding
        the measurement and its standard deviation in the data files.
    :param `use_flags`:
        Whether to keep only the data points whose quality flag is considered good.
    :param `zip_dir`, `use_cached_datafiles`:
        Passed on to `get_dataset`.
    :return:
        One `LoadedDataset` per data object holding data about `tracer`, in the order of `dobjs`.
    """

    def get_datetime(s: pd.Series) -> datetime:
        return datetime(s['Year'], s['Month'], s['Day'], s['Hour'], s['Minute'], tzinfo=timezone.utc)

    loaded_datasets: list[LoadedDataset] = []
    for dobj in dobjs:
        for data_type, spec in tracer.specs.items():
            if dobj.specification.self.uri == spec:
                dataset: pd.DataFrame = get_dataset(dobj, zip_dir, use_cached_datafiles)
                # Before the flag filtering, which relies on the flags this corrects.
                dataset = mask_sentinels(
                    dataset, tracer, GOOD_FLAGS_PER_TYPE[data_type], dobj.fileName)
                dataset = dataset.rename(
                    {'DecimalDate': 'JulDate', tracer.value_column: 'Meas',
                     tracer.std_column: 'Stdev'}, axis=1)
                dataset['Datetime'] = dataset.apply(get_datetime, axis=1)
                dataset['Level'] = DATA_LEVEL_PER_TYPE[data_type]
                if use_flags:
                    dataset = dataset[dataset['Flag'].isin(GOOD_FLAGS_PER_TYPE[data_type])]
                loaded_datasets.append(LoadedDataset(dobj=dobj, data_type=data_type, data=dataset))
    return loaded_datasets

def combine_datasets(
        loaded_datasets: list[LoadedDataset], station_id: str, sampling_height: float,
        tracer: Tracer) -> tuple[pd.DataFrame, list[DataObject]]:
    """
    Combine the datasets of a given station and sampling height into a single one.
    Performs no I/O; the datasets are read beforehand by `load_datasets`.
    :param `loaded_datasets`:
        The datasets of the station and sampling height, as returned by `load_datasets`.
    :param `station_id`:
        Station ID code.
    :param `sampling_height`:
        Sampling height in meters.
    :param `tracer`:
        The tracer being processed.
    :return:
        A pandas DataFrame combining all datasets and the list of data objects that were used.
    """
    data_per_type: dict[str, pd.DataFrame] = {}
    hashsums_of_used_dobjs: dict[str, list[str]] = {}
    for loaded_dataset in loaded_datasets:
        dobj = loaded_dataset.dobj
        data_type = loaded_dataset.data_type
        dataset = loaded_dataset.data
        # There should be at most one dataset of each type for a given station and sampling height.
        # If more than one is found, keep the one with the most recent data unless the additional
        # datasets were added manually among the deprecated datasets that need to be included.
        if data_type in data_per_type.keys():
            deprecated_dobjs_at_sampling_height = (
                deprecated_dobjs_to_use.get(tracer.key, {})
                .get(station_id, {})
                .get(sampling_height, []))
            additional_dobj_is_needed = (
                f'https://meta.icos-cp.eu/objects/{dobj.hash[:24]}'
                in deprecated_dobjs_at_sampling_height)
            if additional_dobj_is_needed:
                if dataset['Datetime'].iloc[-1] < data_per_type[data_type]['Datetime'].iloc[0]:
                    data_per_type[data_type] = pd.concat([dataset, data_per_type[data_type]])
                    hashsums_of_used_dobjs[data_type].append(dobj.hash)
                elif dataset['Datetime'].iloc[0] > data_per_type[data_type]['Datetime'].iloc[-1]:
                    data_per_type[data_type] = pd.concat([data_per_type[data_type], dataset])
                    hashsums_of_used_dobjs[data_type].append(dobj.hash)
                else:
                    print(
                        f'Overlap in time between multiple datasets of type "{data_type} for station'
                        f' {station_id} at sampling height {sampling_height} m. Datasets were not'
                        ' merged.')
            else:
                print(
                    f'More than one dataset of type "{data_type}" was found when processing'
                    f' station {station_id} at sampling height {sampling_height} m.'
                    ' The dataset with the most recent data is used.')
                if dataset['Datetime'].iloc[-1] < data_per_type[data_type]['Datetime'].iloc[-1]:
                    continue
                else:
                    data_per_type[data_type] = dataset
                    hashsums_of_used_dobjs[data_type] = [dobj.hash]
        else:
            data_per_type[data_type] = dataset
            hashsums_of_used_dobjs.setdefault(data_type, []).append(dobj.hash)

    hashsums_of_all_used_dobjs: list[str] = [
        hashsum for hashsums in hashsums_of_used_dobjs.values() for hashsum in hashsums]
    used_dobjs: list[DataObject] = [
        loaded_dataset.dobj for loaded_dataset in loaded_datasets
        if loaded_dataset.dobj.hash in hashsums_of_all_used_dobjs]

    full_dataset = merge_by_priority(data_per_type, station_id, sampling_height)
    return full_dataset.set_index('Datetime'), used_dobjs

def merge_by_priority(
        data_per_type: dict[str, pd.DataFrame], station_id: str, sampling_height: float
        ) -> pd.DataFrame:
    """
    Combine the datasets of the different data types into a single chronological one.

    Two orderings are at play. The **priority on overlap**, which decides which data type wins
    where two of them cover the same period, is: 'L2' over 'historic', 'L2' over 'fasttrack',
    and 'fasttrack' over 'nrt'. Every 'L2' row is therefore always kept, and 'historic' only
    contributes rows from before the level-2 data begins. The **concatenation sequence**, which
    is merely chronological, is 'historic' -> 'L2' -> 'fasttrack' -> 'nrt': each of the last two
    contributes only the rows that are more recent than everything already included.

    The boundaries come from the data itself rather than from the temporal interval reported in
    the metadata of the data objects. The two do not always agree, and where they disagree using
    the metadata either leaves a gap (when a dataset's interval starts before its first row, the
    preceding data type having already been cut) or produces duplicated timestamps (when the
    interval starts after the first row). Note that this means data that a level-2 reprocessing
    deliberately removed at the very beginning or the very end of its period can be filled in
    again from another data type.

    Every dataset is assumed to be sorted by time, which the source files are.
    :param `data_per_type`:
        One dataset per data type, as collected by `combine_datasets`.
    :param `station_id`, `sampling_height`:
        Only used to report overlaps between data types.
    :return:
        A pandas DataFrame combining the datasets, or an empty one if there is no data at all.
    """
    datasets_to_concatenate: list[pd.DataFrame] = []
    # Latest timestamp among the rows included so far.
    latest_datetime: datetime | None = None

    def add(data_type: str, dataset: pd.DataFrame) -> None:
        nonlocal latest_datetime
        if dataset.empty:
            return
        datasets_to_concatenate.append(dataset)
        latest_datetime = dataset['Datetime'].iloc[-1]
        print(
            f'  {data_type} contributed {len(dataset)} row(s) for'
            f' {dataset["Datetime"].iloc[0]} - {dataset["Datetime"].iloc[-1]}.')

    def report_overlap(data_type: str, rows_to_keep: pd.Series) -> None:
        """Report the rows a data type loses to a data type of a higher priority."""
        if not rows_to_keep.all():
            print(
                f'Overlap between {data_type} data and data of a higher priority for station'
                f' {station_id} at sampling height {sampling_height} m.')

    historic = data_per_type.get('historic')
    level_2 = data_per_type.get('L2')
    if level_2 is not None and not level_2.empty:
        if historic is not None:
            rows_to_keep = historic['Datetime'] < level_2['Datetime'].iloc[0]
            report_overlap('historic', rows_to_keep)
            add('historic', historic[rows_to_keep])
        add('L2', level_2)
    elif historic is not None:
        add('historic', historic)

    for data_type in ['fasttrack', 'nrt']:
        dataset = data_per_type.get(data_type)
        if dataset is None or dataset.empty:
            continue
        if latest_datetime is not None:
            rows_to_keep = dataset['Datetime'] > latest_datetime
            report_overlap(data_type, rows_to_keep)
            dataset = dataset[rows_to_keep]
        add(data_type, dataset)

    if not datasets_to_concatenate:
        return pd.DataFrame()
    return pd.concat(datasets_to_concatenate)

# Negative numbers made of nines, possibly followed by zeros: -9, -9.99, -999.9, -999.99, and
# -999990 as found in a few historic files. Deliberately broad: anything matching it that is not
# the expected sentinel is reported.
SENTINEL_SHAPE = re.compile(r'-9+(\.9+)?|-9{3,}0+')


def looks_like_a_sentinel(values: pd.Series) -> pd.Series:
    """Whether each value has the shape of a sentinel; see `SENTINEL_SHAPE`."""
    shaped = pd.Series(False, index=values.index)
    negative = values < 0
    if negative.any():
        shaped[negative] = [bool(SENTINEL_SHAPE.fullmatch(f'{v:.10g}')) for v in values[negative]]
    return shaped


def mask_sentinels(
        dataset: pd.DataFrame, tracer: Tracer, good_flags: list[str], source: str) -> pd.DataFrame:
    """
    Turn the sentinels of a source dataset into genuine missing data.

    Works on the source column names, column by column, so that a sentinel in one column leaves
    the others alone: a missing standard deviation does not make the measurement missing.

    - A value equal to the column's expected sentinel (`tracer.sentinels`) is missing.
    - Any other value shaped like a sentinel is reported. It is treated as missing too, unless
      the column also holds genuine negative values, in which case it may be a real measurement
      and is left as it is.
    - Where the measured value is missing but the flag is a good one, the flag is replaced by
      `SENTINEL_VALUE_FLAG`, so that the row is dropped by flag filtering like any other bad one.
      This has to happen before that filtering.

    Missing float values become NaN, which `data_writer` writes as `FLOAT_FILL_VALUE`. Integer
    columns cannot hold NaN, so theirs become `INT_FILL_VALUE`. Rows are never removed.
    :param `dataset`:
        A dataset as read from a data object, before its columns are renamed.
    :param `tracer`:
        The tracer being processed.
    :param `good_flags`:
        The flags considered good for the data type of the dataset.
    :param `source`:
        Names the data object in the messages.
    :return:
        The dataset with its sentinels masked.
    """
    dataset = dataset.copy()
    for column, sentinel in tracer.sentinels.items():
        if column not in dataset.columns:
            continue
        values = dataset[column]
        expected = values == sentinel.value
        unexpected = looks_like_a_sentinel(values) & ~expected
        if unexpected.any():
            counts = ', '.join(
                f'{value:g} on {count} row(s)' for value, count in values[unexpected].value_counts().items())
            action = 'left as is' if sentinel.negatives_are_valid else 'masked'
            print(
                f'Warning: {source}: column {column} holds {counts}, which look like a sentinel but'
                f' differ from the expected {sentinel.value:g}; {action}.')
        missing = expected if sentinel.negatives_are_valid else expected | unexpected
        if not missing.any():
            continue
        if column == tracer.value_column and 'Flag' in dataset.columns:
            wrongly_good = missing & dataset['Flag'].isin(good_flags)
            if wrongly_good.any():
                print(
                    f'Warning: {source}: {wrongly_good.sum()} row(s) hold a sentinel value under a'
                    f' good flag; flagged {SENTINEL_VALUE_FLAG} instead.')
                dataset.loc[wrongly_good, 'Flag'] = SENTINEL_VALUE_FLAG
        if pd.api.types.is_integer_dtype(values):
            dataset.loc[missing, column] = INT_FILL_VALUE
        else:
            dataset.loc[missing, column] = np.nan
    return dataset

def get_dataset(dobj: DataObject, zip_dir: Path, use_cached_datafiles: bool) -> pd.DataFrame:
    path_to_file = Path(zip_dir, dobj.fileName)
    print(f'  Processing file {path_to_file}...')
    if not path_to_file.exists() or not use_cached_datafiles:
        filename = data.save_to_folder(f'https://meta.icos-cp.eu/objects/{dobj.hash[:24]}', str(zip_dir))
        path_to_file = Path(zip_dir, filename)
    if path_to_file.suffix == '.zip':
        zf = ZipFile(path_to_file, 'r')
        datafiles = [
            f for f in zf.namelist() if f[::-1].replace('.', '_', 1)[::-1] == dobj.fileName.strip('.zip')]
        if len(datafiles) > 1:
            print(
                f'More than one file was found in the archive "{path_to_file.name}" that matches '
                f'the data object\'s file name.\nUsing {datafiles[0]}.')
        buffer = BytesIO(zf.open(datafiles[0]).read())
        zf.close()
        dataset = _read_data_from_csv_without_headers(buffer, dtype={'OriginalFlag': 'object'})
    else:
        buffer = BytesIO(open(path_to_file, 'rb').read())
        dataset = _read_data_from_csv_without_headers(buffer)
    buffer.close()

    if dataset.columns[0] != 'Site':
        print(f'Dataset in archive {path_to_file} might have been processed improperly.')

    return dataset

def _read_data_from_csv_without_headers(
        buffer: BytesIO, dtype: dict[str, DtypeArg] | None = None) -> pd.DataFrame:
    """
    Read a CSV file without headers.
    :param `buffer`:
        Path to the CSV file or a file-like object.
    :param `dtype`:
        A dictionary specifying the data types for (some of) the columns.
    :return:
        A pandas DataFrame with the data from the CSV file.
    """
    line = b"#"
    while line not in {b"#\n", b"#\r\n", b""}:
        line = buffer.readline()
    columns = buffer.readline().decode('utf-8').strip('#\n').split(';')
    return pd.read_table(buffer, delimiter=';', names=columns, dtype=dtype)

def _prompt_for_timezone(station_id: str) -> float:
    """
    Prompt the user for a time zone value.
    :param `station_id`:
        A string representing the ID of the station.
    :return:
        A float representing the time zone value.
    """
    info_text = (
        f'Please provide the time zone of station {station_id} in hours (e.g., 1.0 for UTC+1,'
        ' -2.0 for UTC-2): ')
    tz = _prompt_for_float_value(info_text)
    return tz

def _prompt_for_float_value(info_text: str) -> float:
    tz = None
    while not isinstance(tz, float):
        try:
            tz = float(input(info_text))
        except ValueError:
            tz = None
    return tz

if __name__ == '__main__':
    main()
