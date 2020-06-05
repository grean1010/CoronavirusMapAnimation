#######################################################################################
## Title:   create_corona_maps.py
## Author:  Maria Cupples Hudson
## Purpose: Read historical monthly unemployment from spreadsheets into a dataframe\
## Updates: 10/14/2019 Code Written
##          06/03/2020 Updated to work with Coronavirus data
#######################################################################################
##
##
#######################################################################################
import folium
import pandas as pd
import json
import csv 
import os
import time
import datetime
from selenium import webdriver
from create_timepoint_maps import make_map


# location of this folder on the hard drive
base_loc = os.path.join('C:\\','Users','laslo','OneDrive','Documents','Maria','CoronavirusMapAnimation')

# Set locations for raw and clean data folders.
raw_loc = os.path.join('RawData')
clean_loc = os.path.join('CleanData')

map_html = os.path.join(base_loc,'map_html')
map_png = os.path.join(base_loc,'map_png')

#######################################################################################
## Import coronavirus case data by county and month
#######################################################################################

# Read each of three sheets into a data frame
cdata = os.path.join(raw_loc,'covid_confirmed_usafacts.csv')
covid = pd.read_csv(cdata)

countydata = os.path.join(raw_loc,'covid_county_population_usafacts.csv')
countypop = pd.read_csv(countydata)

deathdata = os.path.join(raw_loc,'covid_deaths_usafacts.csv')
deaths = pd.read_csv(deathdata)

allcases = pd.merge(covid,countypop,on=['countyFIPS','County Name','State'])
alldeaths = pd.merge(deaths,countypop,on=['countyFIPS','County Name','State'])

# Pull the column names and prepare list for renaming. We only do this for the cases
# since the death data is in the same format. We can create a rename list for both.
cols_in = allcases.columns
case_rename = []
death_rename = []

# Use the column titles to either rename to desired name or flag the column to be dropped
for col in cols_in:
    
    # If this is a date column then pull the date information from the column name.
    if '/' in col:
        col_month = col[0:col.find('/')]
        col_day = col[col.find('/')+1:col.find('/',col.find('/')+1)]
        if len(col_month) == 1:
            col_month = f'0{col_month}'
        if len(col_day) == 1:
            col_day = f'0{col_day}'

        # Create renames for cases and deaths
        case_rename.append(f'cases_2020{col_month}{col_day}')
        death_rename.append(f'deaths_2020{col_month}{col_day}')
        
    elif col == 'countyFIPS':
        case_rename.append('FIPS')
        death_rename.append('FIPS')
    elif col == 'County Name':
        case_rename.append('CountyName')
        death_rename.append('CountyName')
    elif col == 'State':
        case_rename.append('StateAbbr')
        death_rename.append('StateAbbr')
    elif col == 'stateFIPS':
        case_rename.append('DROP')
        death_rename.append('DROP')
    else:
        case_rename.append(col)
        death_rename.append(col)

# Reset the column names
allcases.columns = case_rename
alldeaths.columns = death_rename

# Get rid of dropped columns
allcases.drop(columns =['DROP'], inplace = True) 
alldeaths.drop(columns =['DROP'], inplace = True) 

# Merge cases and deaths together now that they have distinct names
# Then drop state totals (FIPS = 0) so we are left with only county-level information.
alldata = pd.merge(allcases,alldeaths,on=['FIPS', 'CountyName', 'StateAbbr', 'population'])
alldata = alldata.loc[(alldata["FIPS"] != 0), :].reset_index()

# Initialize county and state fips and state abbreviation as character
alldata['STATEFP'] = ''
alldata['COUNTYFP'] = ''

# Make sure the fips codes have leading zeros. Excel drops these if it considered it a numeric value.
for obs in range(0,len(alldata)):
    if len(str(alldata.loc[obs,'FIPS'])) == 4:
        alldata.loc[obs,'FIPS'] = f"0{alldata.loc[obs,'FIPS']}"
    else:
        alldata.loc[obs,'FIPS'] = f"{alldata.loc[obs,'FIPS']}"
        
# Grab the current column order
cols_reorder = alldata.columns.to_list()

# take out the columns we are moving to the front
cols_reorder.remove('STATEFP')
cols_reorder.remove('COUNTYFP')
cols_reorder.remove('FIPS')
cols_reorder.remove('StateAbbr')
cols_reorder.remove('CountyName')

# Move the columns we want to the front
cols_reorder.insert(0,'StateAbbr')
cols_reorder.insert(0,'CountyName')
cols_reorder.insert(0,'COUNTYFP')
cols_reorder.insert(0,'STATEFP')
cols_reorder.insert(0,'FIPS')

# reset the column order
alldata = alldata[cols_reorder]


#######################################################################################
## Create a function to set county color based on value
#######################################################################################

def covid_colors(feature,var2map):
    
    try: 
        test_value = feature['properties'][f'{var2map}']
    except:
        test_value = -1
        
    #print(f'var2map = {var2map}   test_value = {test_value}')
    
    # Set the color scheme to be used in the map
    if var2map == 'Cases':
        color_list = case_colors
    elif var2map == 'Deaths':
        color_list = death_colors
    elif var2map == 'Cases Per Million':
        color_list = cpm_colors
    elif var2map == 'Deaths Per Million':
        color_list = dpm_colors

    """Maps low values to green and high values to red."""
    if test_value > color_list[9]:
        return '#a50026' 
    elif test_value > color_list[8]:
        return '#d73027'
    elif test_value > color_list[7]:
        return '#f46d43'
    elif test_value > color_list[6]:
        return  '#fdae61' 
    elif test_value > color_list[5]:
        return '#fee08b'
    elif test_value > color_list[4]:
        return '#d9ef8b'
    elif test_value > color_list[3]:
        return '#a6d96a'
    elif test_value > color_list[2]:
        return '#66bd63'
    elif test_value > color_list[1]:
        return '#1a9850' 
    elif test_value > color_list[0]:
        return '#006837'
    else:
        return "#lightgray"
       
#######################################################################################
## Create a function to create a geojson file for each each point in time with all of
## the data we will use to create maps for that particular date.
#######################################################################################
def make_geofile(timepoint):

    import datetime
    import folium
    import json
        
    # pull the year from the date variable
    year2check = int(timepoint[0:4])

    # for years after 2000, we only have one input file per year labeled as year0101
    json_input = os.path.join(clean_loc,f'FinalGeoFile{timepoint}.json')

    json_output = os.path.join(clean_loc,f'CovidGeoFile{timepoint}.json')
    
    ratedata4timepoint = {}

    # Loop through the dataframe and add information to the data2add dictionary. 
    # We will use this to put these values into the geojson.
    for row, rowvals in alldata.iterrows():
        
        # pull the fips code from the first entry in the row
        FIPS = rowvals[0]
    
        # If we have not previously seen this fips code, add it ot the dictionary
        if FIPS not in ratedata4timepoint:
            ratedata4timepoint[FIPS]={}
            
        # pull county name, state abbreviation and all other info for this timepoint
        ratedata4timepoint[FIPS]['CountyName'] = rowvals[cols_reorder.index('CountyName')]   
        ratedata4timepoint[FIPS]['StateAbbr'] = rowvals[cols_reorder.index('StateAbbr')]  
        ratedata4timepoint[FIPS]['Population'] = rowvals[cols_reorder.index(f'population')]  
        ratedata4timepoint[FIPS]['Cases'] = rowvals[cols_reorder.index(f'cases_{timepoint}')]  
        ratedata4timepoint[FIPS]['Deaths'] = rowvals[cols_reorder.index(f'deaths_{timepoint}')]  
        if rowvals[cols_reorder.index(f'population')] > 0:
            ratedata4timepoint[FIPS]['Cases Per Million'] = rowvals[cols_reorder.index(f'cases_{timepoint}')]  / (rowvals[cols_reorder.index(f'population')] / 1000000)
            ratedata4timepoint[FIPS]['Deaths Per Million'] = rowvals[cols_reorder.index(f'deaths_{timepoint}')]  / (rowvals[cols_reorder.index(f'population')] / 1000000) 
        else:
            ratedata4timepoint[FIPS]['Cases Per Million'] = 0
            ratedata4timepoint[FIPS]['Deaths Per Million'] = 0
            
    # Add the data we will be mapping to the json file
    # Create a blank geojson that we will build up with the existing one plus the new information
    geojson = {}
    
    # Open up the existing geojson file and read it into the empty geojson dictionary created above.
    # While reading it in, pull the matching fips from the data2add dictionary so we can add the
    # variable as a feature/property in the geojson.
    with open(json_input, 'r') as f:
        geojson = json.load(f)
        for feature in geojson['features']:
            featureProperties = feature['properties']
            FIPS = featureProperties['FIPS']

            featureData = ratedata4timepoint.get(FIPS, {})
            for key in featureData.keys():
                featureProperties[key] = featureData[key]
                
    # Output this updated geojson.
    with open(json_output, 'w') as f:
        json.dump(geojson, f)

#######################################################################################
## Create a function to create a the html file containing maps with all of the 
## information in the tooltip and colored by the specified feature.
#######################################################################################

def make_map(timepoint,SaveName,var2map):
    
    # pull the year from the date variable
    year2check = int(timepoint[0:4])

    # for years after 2000, we only have one input file per year labeled as year0101
    json_input = os.path.join(clean_loc,f'FinalGeoFile{timepoint}.json')
    json_output = os.path.join(clean_loc,f'CovidGeoFile{timepoint}.json')
    save_html = os.path.join(map_html,f'{SaveName}_{timepoint}.html')
    save_png = os.path.join(map_png,f'{SaveName}_{timepoint}.png')
    
    # Pull the year and month from the timepoint 
    yearpoint = timepoint[0:4]
    monthpoint = datetime.date(int(timepoint[0:4]), int(timepoint[4:6]), int(timepoint[6:8])).strftime('%B')
    daynum = timepoint[6:8]
    mdy = f"{timepoint[0:4]}/{timepoint[4:6]}/{timepoint[6:8]}"

    # Create a list of fields to be included in the tooltip and a list of descriptions for those variables
    # Use the name of the variable to determine the tooltip list contents
    tip_fields = ['CountyName','StateAbbr','Population','Cases','Deaths','Cases Per Million','Deaths Per Million']
    tip_aliases = ['County Name:', 'State:','Population:',f'Cases {mdy}:',f'Deaths {mdy}:',f'Cases Per Million{mdy}:',f'Deaths Per Million {mdy}:']

    # Set the color scheme to be used in the map
    if var2map == 'Cases':
        color_list = case_colors
    elif var2map == 'Deaths':
        color_list = death_colors
    elif var2map == 'Cases Per Million':
        color_list = cpm_colors
    elif var2map == 'Deaths Per Million':
        color_list = dpm_colors
        
    #print(color_list)
    
   
    m = folium.Map([43,-100], tiles='cartodbpositron', zoom_start=4.25)

    # Display the month on the top of the page
    title_html = f'''
        <div style="position: fixed; 
                 bottom: 90%;
                 right: 50%;
                 align: center;
                 z-index: 1001;
                 padding: 6px 8px;
                 font: 40px Arial, Helvetica, sans-serif;
                 font-weight: bold;
                 line-height: 18px;
                 color: 'black';">
        <h3><b><center><br>Coronavirus {var2map} <br>{monthpoint} {daynum}, {yearpoint} </center></b></h3></div>'''

    m.get_root().html.add_child(folium.Element(title_html))

    # Create legend text
    legend_html = f'''
         <div style="position: fixed; 
                     bottom: 5%;
                     right: 5%;
                     z-index: 1000;
                     padding: 6px 8px;
                     width: 120px;
                     font: 12px Arial, Helvetica, sans-serif;
                     font-weight: bold;
                     background: #8d8a8d;
                     border-radius: 5px;
                     box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
                     line-height: 18px;
                     color: 'black';">


         <i style="background: #a50026"> &nbsp &nbsp</i> {color_list[9]}+ <br>
         <i style="background: #d73027"> &nbsp &nbsp</i> {color_list[8]} - {color_list[9]}<br>
         <i style="background: #f46d43"> &nbsp &nbsp</i> {color_list[7]} - {color_list[8]}<br>
         <i style="background: #fdae61"> &nbsp &nbsp</i> {color_list[6]} - {color_list[7]}<br>
         <i style="background: #fee08b"> &nbsp &nbsp</i> {color_list[5]} - {color_list[6]}<br>
         <i style="background: #d9ef8b"> &nbsp &nbsp</i> {color_list[4]} - {color_list[5]}<br>
         <i style="background: #a6d96a"> &nbsp &nbsp</i> {color_list[3]} - {color_list[4]}<br>
         <i style="background: #66bd63"> &nbsp &nbsp</i> {color_list[2]} - {color_list[3]}<br>
         <i style="background: #1a9850"> &nbsp &nbsp</i> {color_list[1]} - {color_list[2]}<br>
         <i style="background: #006837"> &nbsp &nbsp</i> 0<br>
          </div>
         '''

    
    # Add the legend to the html
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.GeoJson(json_output,
                   style_function=lambda feature: {
                                            'fillColor': covid_colors(feature,f"{var2map}"),
                                            'fillOpacity' : '0.9',
                                            'color' : 'black',
                                            'weight' : 1
                                            },   
                    highlight_function=lambda x: {'weight':2,'fillOpacity':1},    
                    tooltip=folium.features.GeoJsonTooltip(
                                            fields=tip_fields,
                                            aliases=tip_aliases)      
    ).add_to(m)

    # Save the map to an html file
    m.save(save_html)

    # Open a browser window...
    browser = webdriver.Chrome()

    #..that displays the map...
    browser.get(save_html)

    # maximize window
    browser.maximize_window()
    
    # Give the map tiles some time to load
    time.sleep(5)

    # Grab the screenshot and save it as a png file
    browser.save_screenshot(save_png)
    
    # Close the browser
    browser.quit()

#######################################################################################
## Set color schemes for the different maps
#######################################################################################
case_colors = [-1,1,25,50,75,100,250,500,1000,1500]
death_colors = [-1,1,5,10,25,40,75,100,150,200,250]
cpm_colors = [-1,1,50,100,250,500,1000,2500,5000,10000,20000]
dpm_colors = [-1,1,3,7,10,20,45,75,100,250,500,1000,2500,5000,10000]
    
#######################################################################################
## Create maps for each day
#######################################################################################
for month in range(1,13):
    
    if month < 10:
        mm = f'0{month}'
    else:
        mm = f'{month}'

    # Our data start on 1/22/2020. Set the first day of January to the 22nd.  All others to 1.
    if month == 1:
        firstday = 22
    else:
        firstday = 1

    # Determine the last day of the month (plus 1 for loop purposes)
    if month in (1,3,5,7,8,10,12):
        lastday = 32
    elif month in (4,6,9,11):
        lastday = 31
    else:
        lastday = 30

    for day in range(firstday,lastday):
        if day < 10:
            dd = f'0{day}'
        else:
            dd = f'{day}'

        make_geofile(f'2020{mm}{dd}')
        make_map(f'2020{mm}{dd}','CovidCaseMap','Cases')
        make_map(f'2020{mm}{dd}','CovidDeathMap','Deaths')
        make_map(f'2020{mm}{dd}','CovidCasesPerMillionMap','Cases Per Million')
        make_map(f'2020{mm}{dd}','CovidDeathsPerMillionMap','Deaths Per Million')