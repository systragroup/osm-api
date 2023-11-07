
import geopandas as gpd
import numpy as np
import pandas as pd
from typing import *


def test_bicycle_process(links,cycleway_columns,highway_list):
    # if tag is non existant. add it
    for tag in cycleway_columns:
        if tag not in links.columns:
            links[tag] = 'no'
    links = rename_bicycle_tags(links,'cycleway')
    links = rename_bicycle_tags(links,'cycleway:both')
    links = rename_bicycle_tags(links,'cycleway:left')
    links = rename_bicycle_tags(links,'cycleway:right')


    links['combine_cycle_tag'] = links['cycleway'] +' '+ \
                                    links['cycleway:both'] +' '+ \
                                    links['cycleway:left'] +' '+ \
                                    links['cycleway:right'] 


    # simple method. everything with a tag highway is an highway both side. using the road oneway.
    bike_dict={}
    for string in links['combine_cycle_tag'].unique():
        val = string.split(' ')
        if val[0]=='yes':
            bike_dict[string]='yes'
        elif val[0] == 'shared':
            bike_dict[string]='shared'
        elif 'yes' in val[1:]:
            bike_dict[string]='yes'
        elif  'shared' in val[1:]:
            bike_dict[string]='shared'
        else :
            bike_dict[string]='no'
    links['cycleway'] = links['combine_cycle_tag'].apply(lambda x: bike_dict.get(x))
    links.loc[links['highway']=='cycleway','cycleway'] = 'yes'

    links = links.drop(columns = cycleway_columns)
    #remove highway not asked for. (because of cycleway)
    links = links[links['highway'].isin(highway_list)]
    links = links.drop(columns='combine_cycle_tag')
    #links = get_bicycle_oneway(links)
    links['cycleway_reverse'] = links['cycleway']

    
    return links



def rename_bicycle_tags(links: gpd.GeoDataFrame, col:str,inplace: bool = True) -> gpd.GeoDataFrame:
    '''
    replace tags with no, shared or yes.
    inplace = False will create new column with prefix agg_
    '''
    print('original values : ',links[col].unique())
    prefix = '' if inplace else 'agg_'
    links[prefix + col] = links[col]
    # fill NaN with no
    links.loc[links[prefix + col].astype('str').str.lower().isin(['nan','none']),prefix + col] = 'no'
    cycle_dict={'no':'no', 
                'shared':'shared',
                'share_busway':'shared', 
                'shared_lane':'shared'}

    links[prefix + col] = links[prefix + col].apply(lambda x: cycle_dict.get(x, 'yes'))
    print('rename as : ',list(links[prefix + col].unique()))

    return links


def get_bicycle_oneway(links: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    format oneway column for cycleway. oneway = True if there is an inverse link. else False.
    
    '''
    # get bike lanes
    bike_links = links[links['cycleway']!='no'].copy()
    # find links with inverse (or duplicated)
    bike_links['abset'] = [frozenset(el) for el in zip(bike_links['a'], bike_links['b'])]
    abset = bike_links.groupby('abset')[['a']].agg(len)
    oneway_abset = abset[abset['a']>1].index.values
    # Oneway = True for all links without inverse (abset > 1)
    bike_links['oneway'] = False
    bike_links.loc[bike_links['abset'].isin(oneway_abset),'oneway'] = True
    #apply to links
    links.loc[links['cycleway']!='no','oneway'] = bike_links['oneway']
    return links

def extended_bicycle_process(links):
    links['tags'] = links['tags'].astype(str)
    links['tags'] = links['tags'].apply(lambda x: x.replace("'",'"'))
    links['cycleway'] = links.apply(classify_cycleway_tags_with_direction, axis=1)
    links['cycleway_reverse'] = links['cycleway']
    #links.loc[links['cycleway'] == "Dedicated oneway bike path",'cycleway_reverse'] = "No"
    # we have tuple(left,right). cycleway is right lane (in country whit right side driving)
    links['cycleway_reverse'] = links['cycleway_reverse'].apply(lambda x: x[0] if type(x)==tuple  else x )
    links['cycleway'] = links['cycleway'].apply(lambda x: x[1] if type(x)==tuple  else x )

    return links

# tags classification function
def classify_cycleway_tags(df):
    osmTags=df['tags']
    highwayTag=df['highway']
    
    if highwayTag=='cycleway':
        if  osmTags.find('"foot": "no"')>=0 and \
        osmTags.find('"oneway": "yes"')>=0:
            return "Dedicated oneway bike path"
        elif osmTags.find('"foot": "no"')>=0:
            return "Dedicated bike path"
        else:
            return "Shared bike path"
    elif highwayTag=="path":
        if (osmTags.find('"bicycle": "yes"')>=0 or \
        osmTags.find('"bicycle": "designated"')>=0) and \
        osmTags.find('"foot": "no"')>=0:
            return "Dedicated bike path"
        elif osmTags.find('"bicycle": "yes"')>=0 or \
        osmTags.find('"bicycle": "designated"')>=0 and \
        osmTags.find('"foot": "yes"')>=0:
            return "Shared bike path"
        else:
            return "Pedestrian path/street with cycling not allowed"
    elif highwayTag=="footway" or highwayTag=="pedestrian":
        if osmTags.find('"bicycle": "yes"')>=0 or osmTags.find('"bicycle": "designated"')>=0:
            return "Pedestrian path/street with cycling allowed"
        else:
            return "No" #"Pedestrian path/street with cycling not allowed"
    elif highwayTag=="living_street":
        return "Shared zone"
    elif highwayTag=="construction":
        if osmTags.find('"cycleway": "track"')>=0:
            return "Future cycleway"
        else:
            return "Future link"
    else:
        if osmTags.find('"cycleway": "track"')>=0 or \
        osmTags.find('"cycleway": "opposite_track"')>=0 or \
        osmTags.find('"cycleway:left": "track"')>=0 or \
        osmTags.find('"cycleway:both": "track"')>=0 or \
        osmTags.find('"cycleway:right": "track"')>=0:
            return "Protected bike lane"
            
        elif osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        (osmTags.find('"cycleway:left:buffer:right"')>=0 or\
        osmTags.find('"cycleway:both:buffer:right"')>=0 )and \
        (osmTags.find('"cycleway:left:buffer:left"')==-1 or \
        osmTags.find('"cycleway:both:buffer:left"')==-1) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0 and \
        osmTags.find('"cycleway:left:buffer:left"')==-1):
            return "Buffered bike lane (road-side)" 
            
        elif osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        (osmTags.find('"cycleway:left:buffer:left"')>=0 or\
        osmTags.find('"cycleway:both:buffer:left"')>=0 )and \
        (osmTags.find('"cycleway:left:buffer:right"')==-1 or \
        osmTags.find('"cycleway:both:buffer:right"')==-1) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')==-1):
            return "Buffered bike lane (kerb-side)" 
            
        elif osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        ((osmTags.find('"cycleway:left:buffer:both"')>=0 or\
        osmTags.find('"cycleway:both:buffer:both"')>=0 ) or \
        (osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0) or \
        (osmTags.find('"cycleway:both:buffer:left"')>=0 and \
        osmTags.find('"cycleway:both:buffer:right"')>=0)) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        ((osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0) or \
        osmTags.find('"cycleway:left:buffer:both"')>=0)):
            return "Buffered bike lane (both sides)" 
            
        elif osmTags.find('"cycleway": "lane"')>=0 or \
        osmTags.find('"cycleway": "opposite_lane"')>=0 or \
        osmTags.find('"cycleway:left": "lane"')>=0 or \
        osmTags.find('"cycleway:right": "lane"')>=0 or \
        osmTags.find('"cycleway:both": "lane"')>=0:
            if (osmTags.find('"cycleway:both": "lane"')>=0 and \
            (osmTags.find('"cycleway:both:lane": "advisory"')>=0 or \
            osmTags.find('"cycleway:left:lane": "advisory"')>=0)) or\
            osmTags.find('"cycleway:left": "lane"')>=0 and \
            osmTags.find('"cycleway:left:lane": "advisory"')>=0:
                if osmTags.find('"cycleway:left": "lane"')>=0 and \
                osmTags.find('"cycleway:right": "no"')>=0 and \
                osmTags.find('"cycleway:left:lane": "advisory"')>=0:
                    return "Advisory bike lane (single side)"
                else:
                    return "Advisory bike lane"
            elif osmTags.find('"cycleway:both:conditional"')>=0 or \
            osmTags.find('"cycleway:left:conditional"')>=0 or \
            osmTags.find('"cycleway:both:lane:conditional"')>=0 or \
            osmTags.find('"cycleway:left:lane:conditional"')>=0:
                return "Peak hour bike lane"
            else :
                return "Painted bike lane" 
        elif osmTags.find('"cycleway": "shared_lane"')>=0 or \
        (osmTags.find('"cycleway:both": "shared_lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "pictogram"')>=0 or \
        osmTags.find('"cycleway:left:lane": "pictogram"')>=0)) or \
        (osmTags.find('"cycleway:left": "shared_lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "pictogram"')>=0) or \
        (osmTags.find('"cycleway:right": "shared_lane"')>=0 and \
        osmTags.find('"cycleway:right:lane": "pictogram"')>=0):
            return "Sharrow"
        elif osmTags.find('"cycleway:both": "share_busway"')>=0 or \
        osmTags.find('"cycleway:both": "opposite_share_busway"')>=0 or \
        osmTags.find('"cycleway:left": "share_busway"')>=0 or \
        osmTags.find('"cycleway:left": "opposite_share_busway"')>=0:
            return "Bus lane with cycling allowed"
        elif osmTags.find('"cycleway:left": "shoulder"')>=0 or \
        osmTags.find('"cycleway:both": "shoulder"')>=0:
            return "Shoulder cyclable"
        elif osmTags.find('"bicycle": "dismount"')>=0:
            return "Bicyclists dismount"
        elif osmTags.find('"bicycle": "no"')>=0:
            return "No" #"Cycling prohibited"
        elif osmTags.find('"bike"')>=0 or \
        osmTags.find('"cycle"')>=0:
            return "Possible cycling infrastructure/link"
        else:
            return "No" #"Mixed traffic"
        #other

# tags classification function
def classify_cycleway_tags_with_direction(df):
    osmTags=df['tags']
    highwayTag=df['highway']
    res=['No','No']
    if highwayTag=='cycleway':
        if  osmTags.find('"foot": "no"')>=0 and \
        osmTags.find('"oneway": "yes"')>=0:
            return ("No","Dedicated bike path")
        elif osmTags.find('"foot": "no"')>=0:
            return "Dedicated bike path"
        else:
            return "Shared bike path"
    elif highwayTag=="path":
        if (osmTags.find('"bicycle": "yes"')>=0 or \
        osmTags.find('"bicycle": "designated"')>=0) and \
        osmTags.find('"foot": "no"')>=0:
            return "Dedicated bike path"
        elif osmTags.find('"bicycle": "yes"')>=0 or \
        osmTags.find('"bicycle": "designated"')>=0 and \
        osmTags.find('"foot": "yes"')>=0:
            return "Shared bike path"
        else:
            return "Pedestrian path/street with cycling not allowed"
    elif highwayTag=="footway" or highwayTag=="pedestrian":
        if osmTags.find('"bicycle": "yes"')>=0 or osmTags.find('"bicycle": "designated"')>=0:
            return "Pedestrian path/street with cycling allowed"
        else:
            return "No" #"Pedestrian path/street with cycling not allowed"
    elif highwayTag=="living_street":
        return "Shared zone"
    elif highwayTag=="construction":
        if osmTags.find('"cycleway": "track"')>=0:
            return "Future cycleway"
        else:
            return "Future link"
    else:
        if (osmTags.find('"cycleway": "track"')>=0 or \
        osmTags.find('"cycleway": "opposite_track"')>=0 or \
        osmTags.find('"cycleway:both": "track"')>=0 or \
        (osmTags.find('"cycleway:left": "track"')>=0 ) and (~osmTags.find('"cycleway:left:oneway": "yes"')>=0) or \
        (osmTags.find('"cycleway:right": "track"')>=0 ) and (~osmTags.find('"cycleway:right:oneway": "yes"')>=0)) and \
        osmTags.find('"oneway:bicycle": "yes"')==-1 :
            return "Protected bike lane"
        else:
            if osmTags.find('"cycleway:left": "track"')>=0 or \
                osmTags.find('"cycleway:left": "opposite_track"')>=0:
                res[0]="Protected bike lane"
            if osmTags.find('"cycleway:right": "track"')>=0 or \
                osmTags.find('"cycleway:right": "opposite_track"')>=0:
                res[1]="Protected bike lane"
            
        if osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        (osmTags.find('"cycleway:left:buffer:right"')>=0 or\
        osmTags.find('"cycleway:both:buffer:right"')>=0 )and \
        (osmTags.find('"cycleway:left:osm:left"')==-1 or \
        osmTags.find('"cycleway:both:buffer:left"')==-1) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0 and \
        osmTags.find('"cycleway:left:buffer:left"')==-1):
            return "Buffered bike lane (road-side)" 
            
        elif osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        (osmTags.find('"cycleway:left:buffer:left"')>=0 or\
        osmTags.find('"cycleway:both:buffer:left"')>=0 )and \
        (osmTags.find('"cycleway:left:buffer:right"')==-1 or \
        osmTags.find('"cycleway:both:buffer:right"')==-1) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')==-1):
            return "Buffered bike lane (kerb-side)" 
            
        elif osmTags.find('"cycleway:both": "lane"')>=0 and \
        (osmTags.find('"cycleway:both:lane": "exclusive"')>=0 or \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 ) and \
        ((osmTags.find('"cycleway:left:buffer:both"')>=0 or\
        osmTags.find('"cycleway:both:buffer:both"')>=0 ) or \
        (osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0) or \
        (osmTags.find('"cycleway:both:buffer:left"')>=0 and \
        osmTags.find('"cycleway:both:buffer:right"')>=0)) or \
        (osmTags.find('"cycleway:left": "lane"')>=0 and \
        osmTags.find('"cycleway:left:lane": "exclusive"')>=0 and \
        ((osmTags.find('"cycleway:left:buffer:left"')>=0 and \
        osmTags.find('"cycleway:left:buffer:right"')>=0) or \
        osmTags.find('"cycleway:left:buffer:both"')>=0)):
            return "Buffered bike lane (both sides)" 
            
        elif osmTags.find('"cycleway": "lane"')>=0 or \
        osmTags.find('"cycleway": "opposite_lane"')>=0 or \
        osmTags.find('"cycleway:left": "lane"')>=0 or \
        osmTags.find('"cycleway:right": "lane"')>=0 or \
        osmTags.find('"cycleway:both": "lane"')>=0:
            if (osmTags.find('"cycleway:both": "lane"')>=0 and \
            (osmTags.find('"cycleway:both:lane": "advisory"')>=0 or \
            osmTags.find('"cycleway:left:lane": "advisory"')>=0 or \
            osmTags.find('"cycleway:right:lane": "advisory"')>=0)) or \
            (osmTags.find('"cycleway:left": "lane"')>=0 and \
            osmTags.find('"cycleway:left:lane": "advisory"')>=0) or \
            (osmTags.find('"cycleway:right": "lane"')>=0 and \
            osmTags.find('"cycleway:tight:lane": "advisory"')>=0)    :
                if osmTags.find('"cycleway:left": "lane"')>=0 and \
                osmTags.find('"cycleway:right": "no"')>=0 and \
                osmTags.find('"cycleway:left:lane": "advisory"')>=0:
                     res[0] = "Advisory bike lane"
                if osmTags.find('"cycleway:right": "lane"')>=0 and \
                osmTags.find('"cycleway:left": "no"')>=0 and \
                osmTags.find('"cycleway:right:lane": "advisory"')>=0:
                     res[1] = "Advisory bike lane"   
                else:
                    return "Advisory bike lane"
            elif osmTags.find('"cycleway:both:conditional"')>=0 or \
            osmTags.find('"cycleway:left:conditional"')>=0 or \
            osmTags.find('"cycleway:both:lane:conditional"')>=0 or \
            osmTags.find('"cycleway:left:lane:conditional"')>=0:
                return "Peak hour bike lane"
            else :
                if osmTags.find('"cycleway": "lane"')>=0 or \
                osmTags.find('"cycleway": "opposite_lane"')>=0 or \
                osmTags.find('"cycleway:both": "lane"')>=0 or \
                osmTags.find('"oneway:bicycle": "yes"')==-1:
                    return "Painted bike lane" 
                if osmTags.find('"cycleway:left": "lane"')>=0:
                    res[0] =  "Painted bike lane" 
                if osmTags.find('"cycleway:right": "lane"')>=0:
                    res[1] =  "Painted bike lane" 
        if osmTags.find('"cycleway": "shared_lane"')>=0 or \
        (osmTags.find('"cycleway:both": "shared_lane"')>=0 and \
        osmTags.find('"cycleway:both:lane": "pictogram"')>=0):
            return "Sharrow"
        else:
            if osmTags.find('"cycleway:left:lane": "pictogram"')>=0 or \
            osmTags.find('"cycleway:left": "shared_lane"')>=0:
                res[0] = "Sharrow"
            if osmTags.find('"cycleway:right:lane": "pictogram"')>=0 or \
            osmTags.find('"cycleway:right": "shared_lane"')>=0:
                res[1] = "Sharrow"
        
        if osmTags.find('"cycleway:both": "share_busway"')>=0 or \
        osmTags.find('"cycleway:both": "opposite_share_busway"')>=0 or \
        osmTags.find('"cycleway:left": "share_busway"')>=0 or \
        osmTags.find('"cycleway:left": "opposite_share_busway"')>=0:
            return "Bus lane with cycling allowed"
        elif osmTags.find('"cycleway:left": "shoulder"')>=0 or \
        osmTags.find('"cycleway:both": "shoulder"')>=0:
            return "Shoulder cyclable"
        elif osmTags.find('"bicycle": "dismount"')>=0:
            return "Bicyclists dismount"
        elif osmTags.find('"bicycle": "no"')>=0:
            return "No" #"Cycling prohibited"
        elif osmTags.find('"bike"')>=0 or \
        osmTags.find('"cycle"')>=0:
            return "Possible cycling infrastructure/link"
        else:
            return tuple(res)#"Mixed traffic"
        #other