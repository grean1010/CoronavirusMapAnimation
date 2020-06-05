#######################################################################################
## Title:   create_timepoint_geojson_after2000.py
## Author:  Maria Cupples Hudson
## Purpose: Create json files for distinct points in time using historical shape
##          files downloaded from the Atlas of Historical County Boudaries. This code
##          creates a function that can be called by other programs.
##          Note that this program focuses on years after 2000, which were not part
##          of the download from the aAtlas of Historical County Boudaries.  Instead
##          these files were downloaded from the Census Bureau.
## Updates: 10/14/2019 Code Written
##
#######################################################################################
##
## Shape files were downloaded from this site:
##   https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2000.html
##
## Next, we turned these into geojson format by using this site:
##   https://mapshaper.org/
##
## The resulting json files are the input to this program.
## 
## Dependencies:  json, datetime, os
##
#######################################################################################\
import json
import os
import datetime

# Set locations for raw and clean data folders.
raw_loc = os.path.join('RawData')
clean_loc = os.path.join('CleanData')

# File location for the downloaded geojson file. Note that we used the .05 degree tolerance
# version of the file.  More finely detailed, but larger files have the same structure and
# could be subtituted here.
json_loc = os.path.join('..','countyMapData')

# Create a geojson file for a given point in time by pulling records from the big/historical
# geojson file and keeping only records that were active as of that date.  Note that the 
# historical file covers years 1629 to 2000.
def create_timepoint_geojson(timepoint):
    
    # create a reference to the output file
    outfile = os.path.join(clean_loc,f'FinalGeoFile{timepoint}.json')

    print(f"Creating output geojson file {outfile}")

    # pull the year from the date variable
    year2check = int(timepoint[0:4])
    
    # for years greater than 2000 we also need the two digit year
    yr = str(year2check)[2:4]
    
    # create a reference to the input geojson file. Different years have different files/formats
    # The 2019 file is the latest available from Census as of June 2020.
    infile = os.path.join(json_loc,f'cb_2019_us_county_20m.json')

    print(f"Creating geojson file for timepoint: {timepoint}")
    print(f"infile = {infile}")
    print(f"outfile = {outfile}")
   
    # Create a blank geojson for the final result
    geojson = {}
        
    # Open up the existing geojson file and read it into the empty geojson dictionary
    # created above. While reading it in, pull the matching state and county fips from
    # the data2add dictionary so we can add the unemployment info to the geojson.
    with open(infile, 'r') as f:
        geojson = json.load(f)
        
        for feature in geojson['features']:
            
            featureProperties = feature['properties']
            STATEFP = featureProperties['STATEFP']
            COUNTYFP = featureProperties['COUNTYFP']
            FIPS = STATEFP + COUNTYFP
            
            # Make sure FIPS, STATEFP, and COUNTYFP are all consistently defined
            featureProperties['FIPS'] = FIPS
            featureProperties['STATEFP'] = STATEFP
            featureProperties['COUNTYFP'] = COUNTYFP
                
    # Output a new geojson file specific to this year.
    # Output this updated geojson.
    with open(outfile, 'w') as f:
        json.dump(geojson, f)

# Create blank geojson files for all days in 2020 as placeholders.
for month in range(1,13):
    if month < 10:
        mm = f'0{month}'
    else:
        mm = f'{month}'

    # Determine the last day of the month (plus 1 for loop purposes)
    if month in (1,3,5,7,8,10,12):
        lastday = 32
    elif month in (4,6,9,11):
        lastday = 31
    else:
        lastday = 30

    for day in range(1,lastday):
        if day < 10:
            dd = f'0{day}'
        else:
            dd = f'{day}'

        create_timepoint_geojson(f'2020{mm}{dd}')