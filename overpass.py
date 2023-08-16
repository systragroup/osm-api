import os
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from typing import *

def get_overpass_query(bbox: Tuple[float,float,float,float],
                       highway_list: List[str],
                       cycleway_list: Optional[List[str]] = None) -> str:
    '''
    format OverPass query in bbox with a list of Highway to import and
    an optinional list of cycleway to import
    highway_list = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", 
                  "secondary", "secondary_link", "tertiary", "tertiary_link", "residential","cycleway"]
    cycleway_list = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                     "share_busway", "opposite_share_busway", "shared_lane", "lane"]
    '''
    overpass_query ="""
    [out:json][timeout:180];
    (
    """
    overpass_query += ''.join([f'way["highway"="{highway}"]{bbox};\n' for highway in highway_list])
    if cycleway_list:
        overpass_query += ''.join([f'way["cycleway"="{cycleway}"]{bbox};\n' for cycleway in cycleway_list])
    overpass_query +=""" 
    );
    out body;
    >;
    out skel qt;
    """
    return overpass_query

def fetch_overpass(overpassQuery: str,
                    cols: List[str] = ['highway', 'maxspeed', 'oneway'], 
                    wd: str = '/tmp/',
                    filename: str = 'way.geojson') -> None:
    '''
    fetch osm data

    parameters
    ----------
    overpassQuery: overpass query
    cols: list of tags to keep.

    returns
    ----------
    Nothing. save file in tmp/way.geojson
    '''

    print("OVERPASS Request ...")
    overpass_url = 'http://overpass-api.de/api/interpreter'
    response = requests.get(overpass_url, params={'data': overpassQuery})
    data = response.json()

    # Extract elements from response
    print("Convert to GeoPandas ...")
    way = pd.DataFrame([d for d in data['elements'] if d['type'] == 'way']).set_index('id')
    nodes = pd.DataFrame([d for d in data['elements'] if d['type'] == 'node']).set_index('id')

    # Convert elements to GeoPandas 
    way_exploded = way.explode('nodes').merge(nodes[['lat','lon']], left_on='nodes', right_index=True, how='left')
    geom = way_exploded.groupby('id')[['lon', 'lat']].apply(lambda x: LineString(x.values))
    geom.name = 'geometry'
    way = gpd.GeoDataFrame(way.join(geom))

    # Filter tags and write networks
    print("Write (way.geojson) ...")
    tags = pd.DataFrame.from_records(way['tags'].values, index=way['tags'].index)
    cols = [col for col in cols if col in tags.columns]
    print(cols)
    way_tags = way.drop(columns=['nodes', 'tags'], errors='ignore').join(tags[cols])

    # SOME CLEANING ON THE ONEWAY ... Work In Progress
    #way_tags['oneway'].fillna('no', inplace=True)
    #way_tags['oneway'] = way_tags['oneway'].replace('yes', True).replace('no', False).replace('-1', False).replace(-1, False).replace('alternating',False).replace('reversible',False)
    #if len(way_tags['oneway'].unique())>2:
    #    print('WARNING: some oneway tags are not defined',way_tags.unique())
    way_tags.to_file(os.path.join(wd, filename),driver='GeoJSON')

def get_bbox(ls: List[List[float]]) -> Tuple[float,float,float,float]:
    '''
    from a list of coords [[lon, lat], [lon, lat]], ...] get bbox around

    parameters
    ----------
    ls: list of coords

    returns
    ----------
    tuple (lat_min, lon_min, lat_max, lon_max)
    '''
    xmin = min([coord[0] for coord in ls])
    xmax = max([coord[0] for coord in ls])
    ymin = min([coord[1] for coord in ls])
    ymax = max([coord[1] for coord in ls])
    return (ymin, xmin, ymax, xmax)