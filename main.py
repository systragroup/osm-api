import os
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
import boto3

from road import *
from bike import *
from overpass import fetch_overpass, get_overpass_query
from elevation import get_elevation_from_srtm, calc_incline
from io import BytesIO

from shapely.geometry import LineString


bucket_name = os.environ['BUCKET_NAME']

def handler(event, context):
    '''
    event keys :
    bbox : list[float]
    elevation: bool
    highway : list[str]
    callID : str

    '''
    print(event)

    wd = '/tmp/'
    columns = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']

    # add elevation arg. if not provided. set to True
    if 'elevation' in (event.keys()):
        add_elevation = event['elevation']
    else:
        add_elevation = True

    # get bbox and requested highway
    bbox = event['bbox']
    bbox = (*bbox,) # list to tuple
    highway_list = event['highway']
    
    # if cycleway is requested. add cyclway tags to the request.
    # https://wiki.openstreetmap.org/wiki/Map_features#When_cycleway_is_drawn_as_its_own_way_(see_Bicycle)
    cycleway_list = None
    cycleway_columns = ['cycleway:both', 'cycleway:left','cycleway:right']
    if "cycleway" in highway_list:
        cycleway_list = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                        "share_busway", "opposite_share_busway", "shared_lane"]
        columns += cycleway_columns
        columns += ['cycleway']
    
    # Start

    # Overpass API request  
    overpass_query = get_overpass_query(bbox, highway_list, cycleway_list)
    fetch_overpass(overpass_query, columns, wd)
    

    # Create links and nodes netowrks from ways of OSM
    print("Convert ways to links and node ...")
    # do not split direction. we need to fix the oneway tag first.
    links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
    nodes = nodes.set_crs(links.crs)


    #test
    if "cycleway" in highway_list:
        links = test_bicycle_process(links,cycleway_columns,highway_list)



    # convert oneway to bool.
    links = clean_oneway(links)

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
    links['maxspeed'] = links['maxspeed'].apply(lambda x: process_list_in_col(x, float, np.nanmean))
    links['lanes'] = links['lanes'].apply(lambda x: process_list_in_col(x, float, lambda x: np.floor(np.nanmean(x))))
    if 'cycleway' in links.columns:
        # sort and take last. sorted = [no,shared,yes]. so yes or shared if there is a list
        links['cycleway'] = links['cycleway'].apply(lambda x: process_list_in_col(x,str,lambda x: np.sort(x)[-1]))

    for col in ['id', 'type', 'highway','name','surface']:
        links[col] = links[col].apply(lambda x: remove_list_in_col(x,'first'))


    # Fill NaN with mean values by highway
    links = fill_na_col(links, 'highway', 'maxspeed', np.mean)
    links = fill_na_col(links, 'highway', 'lanes', lambda x: np.floor(np.mean(x)))

    # Add length
    print("Write Links and Nodes ...")
    epsg = get_epsg(nodes.iloc[0]['geometry'].y, nodes.iloc[0]['geometry'].x)
    links['length'] = links.to_crs(epsg).length

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
