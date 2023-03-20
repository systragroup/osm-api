import os
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
import boto3

from road import *
from io import StringIO

from shapely.geometry import LineString

bucket_name = os.environ['BUCKET_NAME']
s3 = boto3.resource('s3')

def get_epsg(lat, lon):
    return int(32700 - round((45 + lat) / 90, 0) * 100 + round((183 + lon) / 6, 0))

def handler(event, context):
    wd = '/tmp/'

    # Overpass API request
    print("OVERPASS Request ...")
    overpass_url = 'http://overpass-api.de/api/interpreter'
    overpass_query = event['overpass_query']
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
    way_tags.to_file(os.path.join(wd, 'way.geojson'))

    # Create links and nodes netowrks from ways of OSM
    print("Convert ways to links and node ...")
    links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=True)

    # SOME CLEANING ON THE ONEWAY ... Work In Progress
    links['oneway'].fillna('no', inplace=True)
    links['oneway'] = links['oneway'].replace('yes', True).replace('no', False).replace('-1', False).replace(-1, False)

    # Clean Cul de Sac
    print("Remove Cul de Sac ...")
    links, nodes = main_strongly_connected_component(links, nodes)

    # Add length
    print("Write Links and Nodes ...")
    epsg = get_epsg(nodes.iloc[0]['geometry'].y, nodes.iloc[0]['geometry'].x)
    links['length'] = links.to_crs(epsg).length

    # Add Speed
    links['maxspeed'] = links['maxspeed'].str.replace('mph','').replace('kph', '')
    links['maxspeed'] = pd.to_numeric(links['maxspeed'])
    speed_dict = links.dropna().groupby('highway')['maxspeed'].agg(np.mean).to_dict()
    links.loc[~np.isfinite(links['maxspeed']),'maxspeed'] = links.loc[~np.isfinite(links['maxspeed']),'highway'].apply(lambda x: speed_dict.get(x))

    # Add Time
    links['time'] = links['length']/(links['maxspeed']*1000/3600)

    # Outputs
    links_buffer = StringIO()
    links.to_file(links_buffer)
    s3.Object(bucket_name, 'links.geojson').put(Body=links_buffer.getvalue())

    nodes_buffer = StringIO()
    nodes.to_file(nodes_buffer)
    s3.Object(bucket_name, 'nodes.geojson').put(Body=nodes_buffer.getvalue())
    #links.to_file(os.path.join(wd, 'links.geojson'))
    #nodes.to_file(os.path.join(wd, 'nodes.geojson'))
