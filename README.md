### ICOS Observation Package (ObsPack) Data Products
An application to loop through available ICOS atmosphere data (L1, NRI, historical) and produce per station 
and sample-height ObsPack compatible NetCDF data.

#### Here's a very brief explanation of the YamlConfig dataclass
To reduce the number of global variables in the code, we introduce the dataclass YamlConfig. Some of the 
class' members have an asterisk in their description. It means that the logic behind defining these as 
globals in the original code is not yet fully understood. But we still kept them in the migrated code.
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

### Understanding the obspack upload
Follow the steps below, to upload the next obspack version.
1. Before you run anything, go to [https://doi.icos-cp.eu/](https://doi.icos-cp.eu/) and create a number 
   of needed draft DOIs. You will need one for each gas (ch4, co2, n2o, co?, more?) plus one for the full 
   collection. 
2. For each gas-DOI copy the json from the previous version e.g: 10.18160/FE8D-2APZ and paste it in the new.
   Make sure the "Creators" and "Contributors" fields are correct. Since there are many entries there, check 
   if there are any people/organizations that need to be added or removed. Otherwise, continue to the next 
   step.
3. **PUBLISH THE DOIs.** This is a crucial step to the process because of how the application handles the
   citation string in the `.nc` files. If the DOIs are not published, the `.nc` files will end up with empty 
   citation strings; thus we are going to have to regenerate them. Also, if the "Creators" or "Contributors"
   in the DOI are wrong we need to fix them and regenerate the files. Currently running the application and
   regenerating all the files takes a lot of time, so keep that in mind.
4. Before you run the application, go in the code and search for "2025.1" or "2025.2". At the time of writing 
   this documentation, you will find two instances of that in the file "split_this.py". You need to make sure 
   that these strings are updated to the current fast-track version.  
5. For each gas-DOI run the application (currently the python file split_me.py). You need to input the proper
   values in the config.yml file. Remember, you need to generate all the relevant files (.nc, .json, .png, 
   and .txt). The .nc, .png, and .txt files are needed for the zip archive of each gas and the .json files
   are needed for uploading the standalone .nc files. In previous versions, .json files were wrongly included
   in the zip archives.
6. For each gas-DOI output created in the application, you need to create a zip file, containing all .nc, 
   .png, and .txt files.  
   For example: 
   ```bash
   zip obspack_co2_466_GV_ICOSFT2025.2_20250527.zip nc-files/* txt-files/* png-files/*
   ```
   Notice the gas's name in the zip file name, the fast-track version (2025.2) and the current date. The zip
   archive's contents should be 3 directories (nc-files, png-files, txt-files) with their associated files 
   inside.
7. Use the uploadgui to create a new version for each gas compilation (like the one found here: 
   https://meta.icos-cp.eu/objects/NtZhkUxR7chDt8VLzk4g--Rd). 
   1. Replace the "Pre-existing DOI" field with the DOI you created in step 1.
   2. Update the name of the obspack compilation in the "Title" field. (fast-track version & date)
   3. Update the "Description" field. You need to mention the correct fast-track version and the correct DOI.
   4. Update fields "From" (if need be) and "To" (see step 6). To do this, you need to loop through all the 
      .nc files and find the minimum and maximum values of `start_time`. Make sure to input dates for which 
      we had data for a full day.
   5. Update "Creation date" field under Production.
   6. Lastly, add the .zip file that you generated in step 6 and click "Upload". 
8. IMPORTANT NOTICE: at the time of writing this documentation, the only fields that needed changing were the
   step below 1–5. In future versions of obspack, there might be a need to update more of these fields.
   For each gas-DOI created, go in the DOI application and update these next fields:
   1. "date" subfield in "dates" field. Use the current date.
   2. "description" subfield in "descriptions" field. Replace the FastTrack version with the current one.
      e.g.: from 2025.1 to 2025.2 and update the datacite link with the new doi e.g: from 
      https://commons.datacite.org/doi.org/10.18160/FE8D-2APZ to 
      https://commons.datacite.org/doi.org/10.18160/46A2-7ABA where 46A2-7ABA is the gas-DOI you just 
      drafted.
   3. Field "publicationYear" if need be.
   4. Update the "title" subfield in the "title" field with the new information. E.g.: change 
      "obspack_ch4_466_GV_ICOSFT2025.1_20250120" to "obspack_ch4_466_GV_ICOSFT2025.2_20250516" 
   5. Update the "suffix" subfield in the "doi" field with the new gas-DOI. E.g.: from "FE8D-2APZ" to 
     "46A2-7ABA" where "46A2-7ABA" is the gas-DOI you just drafted.  

