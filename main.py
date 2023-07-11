import os
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
import boto3

from road import *
from elevation import get_elevation_from_srtm, calc_incline
from io import BytesIO

from shapely.geometry import LineString


bucket_name = os.environ['BUCKET_NAME']

def process_list_in_col(col_values,new_type,function):
        if isinstance(col_values, list):
            return  function([new_type(val) for val in col_values])
        else:
            return new_type(col_values)
        
def remove_list_in_col(col_values,method='first'):
    if isinstance(col_values, list):
        if method == 'first':
            return col_values[0]
        else:
            return col_values[-1]
        
    else:
        return col_values
def get_epsg(lat, lon):
    return int(32700 - round((45 + lat) / 90, 0) * 100 + round((183 + lon) / 6, 0))

def handler(event, context):
    wd = '/tmp/'

    # add elevation arg. if not provided. set to True
    if 'elevation' in (event.keys()):
        add_elevation = event['elevation']
    else:
        add_elevation = True

    # Overpass API request
    print("OVERPASS Request ...")
    overpass_url = 'http://overpass-api.de/api/interpreter'
    overpass_query = event['overpassQuery']
    response = requests.get(overpass_url, params={'data': overpass_query})
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
    cols = event['tags']
    way_tags = way.drop(columns=['nodes', 'tags'], errors='ignore').join(tags[cols])

    # SOME CLEANING ON THE ONEWAY ... Work In Progress
    way_tags['oneway'].fillna('no', inplace=True)
    way_tags['oneway'] = way_tags['oneway'].replace('yes', True).replace('no', False).replace('-1', False).replace(-1, False).replace('alternating',False).replace('reversible',False)
    if len(way_tags['oneway'].unique())>2:
        print('WARNING: some oneway tags are not defined',way_tags.unique())
    way_tags.to_file(os.path.join(wd, 'way.geojson'))

    # Create links and nodes netowrks from ways of OSM
    print("Convert ways to links and node ...")
    links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
    nodes = nodes.set_crs(links.crs)

    #remove string in maxspeed
    links = clean_maxspeed(links)

    # make sure the geometry are in the right direction (a->b)
    links = rectify_geometry_direction(links,nodes)

    # remove duplicated links (a-b)
    print("simplifying links ...")
    links = drop_duplicated_links(links)
    
    # simplify. remove deg 2 nodes when possible. group by oneway and highway to merge each links.
    links = simplify(links)

    # split onwway into 2 links a-b, b-a
    links = split_oneway(links)

    # Clean Cul de Sac
    print("Remove Cul de Sac ...")
    links, nodes = main_strongly_connected_component(links, nodes)

    print('removing list in columns ...')
    links['maxspeed'] = links['maxspeed'].apply(lambda x: process_list_in_col(x,float,np.nanmean))
    links['lanes'] = links['lanes'].apply(lambda x: process_list_in_col(x,float,np.nanmean)).apply(lambda x: np.floor(x))
    for col in ['id', 'type', 'highway','name','surface']:
        links[col] = links[col].apply(lambda x: remove_list_in_col(x,'first'))

    # Add length
    print("Write Links and Nodes ...")
    epsg = get_epsg(nodes.iloc[0]['geometry'].y, nodes.iloc[0]['geometry'].x)
    links['length'] = links.to_crs(epsg).length

    # Add Speed
    try:
        speed_dict = links.dropna().groupby('highway')['maxspeed'].agg(np.mean).to_dict()
        links.loc[~np.isfinite(links['maxspeed']),'maxspeed'] = links.loc[~np.isfinite(links['maxspeed']),'highway'].apply(lambda x: speed_dict.get(x))
    except:
        print('fail to convert NaN maxspeed to the average max speed (by highway)')
    try:
        links['lanes'] = pd.to_numeric(links['lanes'])
        lane_dict = links.groupby('highway')['lanes'].agg(np.nanmean).apply(lambda x: np.floor(x)).to_dict()
        links.loc[~np.isfinite(links['lanes']),'lanes'] = links.loc[~np.isfinite(links['lanes']),'highway'].apply(lambda x: lane_dict.get(x))
    except:
        print('fail to convert NaN Lane to the average lanes (by highway)')
    # Add Time
    links['time'] = links['length']/(links['maxspeed']*1000/3600)
    links = links.rename(columns = {'maxspeed' : 'speed'})

    # reindex and remove ununsed nodes
    links = links.reset_index(drop=True)
    links.index = 'road_link_'+links.index.astype(str)
    nodes_set = set(links['a']).union(set(links['b']))
    nodes = nodes.loc[list(nodes_set)].sort_index()

    if add_elevation:
        print('Adding elevation')
        el_dict = get_elevation_from_srtm(nodes)
        nodes['elevation'] = nodes.index.map(el_dict.get)
        # incline from node a to b in deg. neg if going down (if b is lower dans a)
        links['incline'] = calc_incline(links['a'].apply(lambda x: el_dict.get(x)).values,
                                    links['b'].apply(lambda x: el_dict.get(x)).values,
                                    links['length'].values)

    # Outputs
    print('Saving on S3')
    folder = event['callID']
    links.to_file(f's3://{bucket_name}/{folder}/links.geojson', driver='GeoJSON')
    nodes.to_file(f's3://{bucket_name}/{folder}/nodes.geojson', driver='GeoJSON')
    print('Success!')
    #links.to_file(os.path.join(wd, 'links.geojson'))
    #nodes.to_file(os.path.join(wd, 'nodes.geojson'))
