### ICOS Observation Package (ObsPack) Data Products
An application to loop through available ICOS atmosphere data (L1, NRI, historical) and produce per station
and sample-height ObsPack compatible NetCDF data.

#### Here's a very brief explanation of the YamlConfig dataclass
To reduce the number of global variables in the code, we introduce the dataclass YamlConfig.
Some of the class' members have an asterisk in their description. It means that the logic behind defining
these as globals in the original code is not yet fully understood.
But we still kept them in the migrated code.
Here's a breakdown of its members:
- gas: which gas the current run concerns ['co2', 'ch4', 'n2o', ... ]
- *analyse: a boolean that controls whether we filter using the CCGCRV routine from Thonen et al. (1996).
- plot: a boolean that controls whether we dynamically show the generated plots during runtime.
- output: directory of the application's output.
- nc: directory of the generated nc files.
- json: directory of the generated json files.
- *txt: directory of the generated txt files.
- png: directory of the generated png files.
- pickle: directory of the generated pickle files, used for caching and debugging.
- zip: directory of the generated zip files.
- *lab_numbers: location of a csv file in the `input` directory. The csv is read and the member is then
  converted to a pandas DataFrame. This might be an unused member.
- icos_stations: location of a csv file in the `input` directory. The csv is read and the member is then
  converted to a pandas DataFrame.
- header: location of a txt file in the `input` directory. It is used as a template in the code.
- glob_aver: a pandas DataFrame containing the global averages for a specific gas.
- file_contribs: a pandas DataFrame of file contributors.
- col_contribs: a pandas DataFrame of collection contributors.
- d_files: a list of shortened hash sums used as "sources" field when constructing the metadata.
- *mauna_loa: a pandas DataFrame containing the global averages for co2.
- *ml: a pandas DataFrame generated after filtering mauna_loa.
- *glb_avg_ch4: a pandas DataFrame containing global averages for ch4.
- do_png: a boolean that controls whether we generate `.png` files.
- do_txt: a boolean that controls whether we generate `.txt` files.
- debug: a boolean to run the application in debug mode.
- debug_info: a boolean to load metadata from the cache instead of doing an http request.
- refresh_pickles: a boolean to load metadata from the cache instead of doing an http request.
