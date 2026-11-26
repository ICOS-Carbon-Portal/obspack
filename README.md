### ICOS Observation Package (ObsPack) Data Products
An application to loop through available ICOS atmosphere data (L2, FastTrack,
NRT, historical) and produce per station and sampling height ObsPack compatible
`netCDF` data files, as well as corresponding `.txt` data files and `.png`
figures representing the time-series of observations.
<hr>

### Recommended preliminary steps
It is a good routine to verify that the information in the file
[icos_stations.csv](input/icos_stations.csv) is correct and up-to-date before
proceeding with creating ObsPack release files. This table contains the IDs and
names of the labs (organizations) that are responsible for the measurements at
each station, and this information is included in the file name of
the individual ObsPack datasets, as well as in the metadata. The table also
contains the OSCAR IDs of the stations which have been attributed one, and
the timezone in which the stations are located. These values are also part
of the metadata of the ObsPack netCDF files and the timezone is used to
calculate the solar time which is provided in the data.
When data from a new station need to be included in the ObsPack release,
a new entry containing information about the station has to be added to
the table before proceeding with the creation of the ObsPack release files.
It is also advised to verify whether some stations have stopped providing new
data since the previous release, in order to avoid creating new data files
with the exact same content as the previous version. There is currently no
configuration parameter to filter out such cases, as several different
scenarios can happen (it is either just a specific tracer at a given station that
is not measured anymore, or one measurement level has been changed or does not
provide any data anymore, etc.) It is recommended to do some temporary
adjustments directly in the script
[metadata_and_data_processing.py](src/icoscp_obspack/metadata_and_data_processing.py)
in such cases, for example using the variables `tracers_to_skip`,
`sampling_heights_to_skip` or `deprecated_dobjs_to_use`.

### Creating and uploading ObsPack release files (per tracer)
**Steps 2 onward must be repeated per tracer (CO₂, CH₄, N₂O, CO, ²²²Rn, ¹⁴CO₂).**
1. Go to [https://doi.icos-cp.eu/](https://doi.icos-cp.eu/) and create a draft
   DOI for the collection that will contain all datasets (`.nc` files) with
   data about all tracers. Do not add any content to the draft DOI, as this will
   be done later. However, check that the draft DOI is saved by reloading
   the page. It might be necessary to make some small change (any change)
   and update the DOI to make sure that it is saved.
2. Go to [https://doi.icos-cp.eu/](https://doi.icos-cp.eu/) and create a draft
   DOI for the ObsPack data product that will contain all datasets about a
   specific tracer. Do not add any content to the draft DOI, as this will be done
   later. However, check that the draft DOI is saved by reloading the page.
   It might be necessary to make some small change (any change) and update
   the DOI to make sure that it is saved.
3. Use the DOI created under step 2 for the setting **doi** in the
   [configuration file](config.yml). Use the DOI created under step 1 for the
   setting **all_tracers_obspack_doi** in the [configuration file](config.yml).
4. Make all necessary changes to the [configuration file](config.yml).\
   Pay special attention to the settings:
     - **tracer**
     - **doi**
     - **all_tracers_obspack_doi**
     - **dois_for_default_citations**
     - **input**
     - **output**
     - **obspack_product_description**
     - **obspack_product_name**
     - **major_version_for_doi**
     - **minor_version_for_doi**
     - **title_for_doi**
     - **description_for_doi**
     - **subjects_for_doi**
     - **use_only_icos_stations_l1_or_l2**
5. Run the script [`metadata_and_data_processing.py`](src/icoscp_obspack/metadata_and_data_processing.py)
   from the `src` directory (`cd src; python icoscp_obspack/metadata_and_data_processing.py`).
   The application reads `../config.yml`, and the relative paths in the
   configuration file are resolved against the working directory.
6. When all metadata have been processed, a message will inform about how many
   stations and sampling heights have been processed, when were the earliest and
   latest measurements among all processed datasets (this information is needed
   for step 11.4 below), and that a `JSON` file has been
   generated and is available for continuing the DOI minting. Paste the content
   of this file in the draft DOI "Edit as JSON" tab.
7. Publish the DOI.
8. **After** the DOI has been successfully published and is accessible, go back
   to the console where the script was running and press `Enter` to proceed with
   the generation of the data files (`.nc` and `.txt`), figures (`.png`) and
   metadata files (`.json`). The data files and figures are needed for the
   `.zip` archive that will be uploaded as the new version of the full ObsPack
   release for the given tracer. The metadata files are needed to upload individual
   datasets.
9. If the DOI is not accessible when the files are being generated, the script
   will not be able to fetch the citation string attached to the DOI and it will
   be missing in the data files. In such a case, the script has to be run again
   after the DOI is published. When running the script again, it is not
   necessary to update the DOI with the content of the generated `JSON` file, as
   the content does not change if nothing else has changed.
10. Once all files have been generated, create a `.zip` archive containing the
    data files and figures. The root directory of the archive should be named
    according to the ObsPack release (e.g.
    `obspack_ch4_466_GVeu_v11.0_20250818.zip` or
    `obspack_ch4_466_ICOSFT2025.3_20251003.zip`)
    and should contain three directories named `nc`, `txt` and `png` which
    contain the respective data files and figures. Perform a data sanity check
    by examining all png files one by one.
11. Use the [upload GUI](https://meta.icos-cp.eu/uploadgui/) to upload the
    ObsPack release to the data portal. If a previous version of the ObsPack
    release for the given tracer exists (which should be the case for CO2, CH4,
    N2O and CO, but not for the tracers whose first release this is), upload as
    a "New version" and provide the URI of the previous version of the ObsPack
    release for this tracer.
    Then, make the following changes:
    1. Use the DOI you created in step 2 in the "Pre-existing DOI" field.
    2. Update the "Title" field with the title provided in the DOI.
    3. Update the "Description" field with the description provided in the DOI.
       The number of stations/observatories and sampling heights/observation
       levels might need to be updated. Refer to the message mentioned in step 6
       to find the correct values for the current release.
    4. Update the fields "From (UTC)" (if need be) and "To (UTC)". Refer to the
       message mentioned in step 6 to find the correct values for the current
       release. Make sure to input dates for which there is data for a full day.
    5. Update the "GeoJSON" field with the content of the file that has been
       generated by the script and that can be found under
       `{output}/GeoJSON_{tracer}.json`.
    6. Enable the "Production" field.
    7. Add "ICOS (Integrated Carbon Observation System) Research Infrastructure"
       as "Creator".
    8. Update the "Creation date" field under Production. The
       `obspack_creation_date` attribute of any data file can be used as a
       reference.
    9. Add the .zip file that you generated in step 10 and click "Upload".
12. Once the ObsPack release has been uploaded to the data portal, update the
    DOI Target URL in the [DOI application](https://doi.icos-cp.eu/) with the
    URL of the newly uploaded ObsPack release in the data portal.
13. Upload individual datasets to the data portal using the script
    [uploader.py](src/icoscp_obspack/uploader.py), also from the `src` directory
    (`python icoscp_obspack/uploader.py`). Be careful that if
    the content of the table [icos_stations.csv](input/icos_stations.csv) has
    been updated (in particular the `NOAALabNr` values), the name of
    the individually produced ObsPack data files might have changed and
    the affected datasets will not be deprecating their previous version by
    default. In such cases, the `json` files created by running the script have
    to be updated manually to guarantee that the proper datasets are deprecated
    by the new ones.
<hr>

#### Yaml configuration
- **tracer**: which tracer the current run concerns ('co2', 'ch4', 'n2o',
  'co', 'rn' (radon-222) and '14co2' (radiocarbon in CO2) are supported).
  Everything that is specific to one of them — the specifications of the data
  objects to collect, the names of the columns holding the measurement and its
  standard deviation, the units and wording used in the netCDF files, the unit
  conversion, the calibration scale, the plot labels — is described by the
  corresponding entry of `TRACERS` in
  [tracers.py](src/icoscp_obspack/tracers.py). Supporting a new tracer means
  adding an entry there and nothing else.
- **doi**: DOI of the ICOS ObsPack release that is going to be produced (see
  also the step-by-step explanations on how to use the application)
- **all_tracers_obspack_doi**: DOI of the ICOS ObsPack collection that includes
  all datasets with data about all tracers
- **dois_for_default_citations**: list of DOIs of references that must be
  included in all datasets related to ICOS stations (for example
  "10.18160/PP29-9CNZ" and "10.18160/ATM_NRT_CO2_CH4")
- **input**: directory containing input data for the application (defaults to
  `input`, relative to the working directory, i.e. `src/input`; `config.yml`
  sets it to `../input`)
- **output**: directory of the application's outputs (defaults to
  `output/{tracer}`, relative to the working directory, i.e. `src/output/{tracer}`;
  `config.yml` sets it to `../output/{tracer}`, which has to be edited together with
  **tracer**)
- **obspack_product_description**: short description of the ObsPack product,
  which will be used in the comment provided for each individual ObsPack dataset
  and should fit in `It is part of {obspack_product_description} and is intended
  for use in...` (e.g. `the CO2 European Obspack data product (version 11.0)`)
- **obspack_product_name**: name of the ObsPack product (e.g. "GVeu"); can be
  skipped in case only one item combining **obspack_product_name** and
  **obspack_product_version** is needed, in which case the value provided for
  **obspack_product_version** will be used
- **obspack_product_version**: version of the ObsPack product (defaults to
  "v{major_version_for_doi}.{minor_version_for_doi}"); as mentioned on the
  previous line, can also be used as a single identifier combining
  **obspack_product_name** and **obspack_product_version**
- **major_version_for_doi**: major release number of the ObsPack product to be
  used for the DOI creation
- **minor_version_for_doi**: minor revision number of the ObsPack product to be
  used for the DOI creation
- **title_for_doi**: title to use for the creation of the DOI of the ObsPack
  product (the file name will be appended automatically after the title and a
  semicolon and should not be included here)
- **description_for_doi**: description of the ObsPack product to be used for the
  DOI creation
- **subjects_for_doi**: list of subjects relevant to the ObsPack product to be
  included during the creation of the DOI (check older releases for examples)
- **publisher_for_doi**: name of the publisher of the ObsPack product to be used for
  the DOI creation (defaults to "ICOS ERIC - Carbon Portal")
- **resource_type_for_doi**: name of the resource type to be used for the DOI
  creation (defaults to "compressed ZIP archive")
- **format_info_for_doi**: explanations about the content of the file included
  in the ObsPack release (defaults to "Compressed ZIP archive of netcdf and
  ASCII files with space-separated columns. Overview pictures of recent data
  and trend plots since 2010 are provided as bitmaps in png format.")
- **rights_for_doi**: license under which the ObsPack release is published
  (defaults to "Creative Commons Attribution 4.0 International")
- **rights_uri_for_doi**: URI to the license (defaults to
  "https://creativecommons.org/licenses/by/4.0/legalcode")
- **doi_json_file**: path to the file which will be generated by the application
  and will contain the `JSON` formatted content needed to mint a new DOI for the
  ObsPack product (defaults to `{output}/doi_json_{tracer}.json`)
- **info_about_produced_files**: path to the file which will be generated by the
  application and will contain information about all produced netCDF files
  (defaults to `{output}/info_about_produced_files_for_{tracer}.csv`). This file
  was intended to be used for uploading individual ObsPack datasets to the data
  portal, but is not needed for this task anymore.
- **nc**: path to the directory where data files in netCDF format are saved
  (defaults to `{output}/nc`)
- **json**: path to the directory where `JSON` files containing metadata about
  individual ObsPack datasets are saved. These files are intended to be used for
  uploading the datasets to the data portal (defaults to `{output}/json`)
- **txt**: path to the directory where data files in text format are saved
  (defaults to `{output}/txt`)
- **png**: path to the directory where figures are saved (defaults to
  `{output}/png`)
- **pickle**: path to the directory where pickle files containing lists of
  authors/contributors/creators are saved for caching and debugging (defaults to
  `{output}/pickle`)
- **zip**: path to the directory where zip files of datasets downloaded from the
  data portal are cached (defaults to `{output}/zip`)
- **use_only_icos_stations_l1_or_l2**: a boolean that controls whether only data
  from ICOS L1 and L2 stations should be processed (defaults to True)
- **use_cached_datafiles**: a boolean that controls whether cached data files
  should be used, otherwise datasets are re-downloaded (defaults to False)
- **analyse**: a boolean that controls whether the trend of the global average
  reference is calculated using the CCGCRV filtering routine from Thoning et al.
  (1989) to be displayed on the figures (defaults to True). The trend of the
  station's own time-series is always calculated
- **do_png**: a boolean that controls whether figures are generated (defaults to
  True)
- **display_plots**: a boolean that controls whether the generated plots are
  dynamically shown during runtime (defaults to False)
- **do_txt**: a boolean that controls whether `.txt` data files are generated
  (defaults to True)
- **debug**: a boolean that controls whether the application should run in debug
  mode, which controls whether pickle files are used for caching (defaults to
  False)
- **refresh_pickles**: a boolean that controls whether the pickle files should
  be updated during the run (defaults to False). Only relevant when **debug** is
  True
- **use_mauna_loa_for_global_co2**: a boolean that controls whether the
  time-series from Mauna Loa is used instead of the marine BL global average as
  a reference trend in figures of CO2 datasets (defaults to False). Only
  relevant when **tracer** is 'co2'. A global average reference is only available
  for CO2, CH4 and N2O; the figures of the other tracers simply do not show one.
- **use_flags**: a boolean that controls whether only data points with "good"
  quality flags are used in the generated data files (defaults to True)
- **lab_numbers**: path to the `.csv` file containing information about
  measurement laboratories (defaults to `{input}/lab_numbers.csv`)
  (source: https://gml.noaa.gov/ccgg/obspack/labinfo.html). The file is
  currently not read: the lab numbers and names come from **icos_stations**
- **icos_stations**: path to the `.csv` file containing information about ICOS
  and non-ICOS stations and the related measurement laboratories (defaults to
  `{input}/icos_stations.csv`)
- **header**: path to the `.txt` file containing a template for the header of
  the `.txt` data files (defaults to `{input}/header.txt`)
- **default_author_weight**: the default citation weight to use for authors
  whose citation weight is not set in the metadata (defaults to 0)
- **print_timing_messages**: a boolean that controls whether to print messages
  showing information about the time taken by various steps in the metadata and
  data processing (defaults to False)
