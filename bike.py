
import geopandas as gpd
import numpy as np
import pandas as pd
from typing import *


def test_bicycle_process(links,cycleway_columns,highway_list):
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
    prefix = '' if inplace else 'agg_'
    links[prefix + col] = links[col]
    # fill NaN with no
    links.loc[links[prefix + col].astype('str')=='nan',prefix + col] = 'no'
    cycle_dict={'no':'no', 
                'shared':'shared',
                'share_busway':'shared', 
                'shared_lane':'shared'}

    links[prefix + col] = links[prefix + col].apply(lambda x: cycle_dict.get(x, 'yes'))
    print(list(links[prefix + col].unique()))

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