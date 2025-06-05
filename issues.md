### Various issues/warnings/errors detected/observed while running the obsback tool.
- ```bash
  DtypeWarning: Columns (20) have mixed types. Specify dtype option on import or set low_memory=False.
  ret_df = pd.read_csv(source, comment='#', header=None, names=colnames[level], delimiter=';',
  ```
- ```bash
  RuntimeWarning: invalid value encountered in cast
  arr = np.asarray(values, dtype=dtype)
  ```
- ```bash
  Error in time filtering for station WES; plot skipped due to: unsupported operand type(s) for *: 'NoneType'
   and 'float'
  ```
- `if c.gas == 'n2o' and obs_data_df.Site.to_list()[0] in ['HTM', 'SVB']:` This line of code was written, to
  keep the application from crashing. The HTM and SVB .nc files have not been uploaded in the obspack 
  previous versions. So that might be a sign of what's happening. Also, the error has something to do with 
  `pandas` being unable to run this python code:
  ```python
  obs_data_df = obs_data_df[time_end_fast:]
  ```
  This also creates issues when uploading, because even though we skip the generation of .nc files, the .json
  files get created anyway.
- The fast-track version naming here should be somehow automated (also look for other usages of that name in
  the code):
  ```python
  obspack_name = 'obspack_' + c.gas + '_' + str(lab_id) + '_GV_ICOSFT2025.2_' + dt.datetime.now().strftime('%Y%m%d')
  ```
- Expand obspack with co (carbon monoxide).
- When running the application for some weird reason the code could not find the previous version of this
  file: ch4_bir_tower-insitu_56_allvalid-75magl.nc. I checked for this specific file name using the advanced
  search in the portal and no results come up (works with other names). Even though I uploaded the new
  version manually, it still cannot be found using the advanced search. Fortunately, I had already included
  the .nc file in the zip archive.
  
