import os
import numpy as np
from road import *
from bike import *
from overpass import fetch_overpass, get_overpass_query
from elevation import get_elevation_from_srtm, calc_incline
from typing import *

CYCLEWAY_COLUMNS = ['cycleway:both', 'cycleway:left','cycleway:right']
HIGHWAY_COLUMNS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']


def osm_importer(bbox:Tuple[float,float,float,float], 
                 highway_list: List[str],
                 cycleway_list: Optional[List[str]] = None,
                 wd: str = '/tmp/')-> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:

    columns = HIGHWAY_COLUMNS.copy()
    # if cycleway is requested. add cyclway tags to the request.
    # https://wiki.openstreetmap.org/wiki/Map_features#When_cycleway_is_drawn_as_its_own_way_(see_Bicycle)
    if cycleway_list:
        columns += CYCLEWAY_COLUMNS
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

    return links, nodes

def osm_simplify(links: gpd.GeoDataFrame, 
                 nodes: gpd.GeoDataFrame, 
                 highway_list: List[str], 
                 add_elevation: bool = True,
                 split_direction : bool = False):
    
    # simplify Linestring geometry. (remove anchor nodes)
    links.geometry = links.simplify(0.00005)

    #test
    if "cycleway" in links.columns:
        links = test_bicycle_process(links, CYCLEWAY_COLUMNS, highway_list)


    # convert oneway to bool.
    links = clean_oneway(links)

    #remove string in maxspeed
    links = clean_maxspeed(links)

     #remove string in maxspeed
    links = clean_lanes(links)

    # make sure the geometry are in the right direction (a->b)
    links = rectify_geometry_direction(links,nodes)

    # remove duplicated links (a-b)
    print("simplifying links ...")
    links = drop_duplicated_links(links)
    
    # simplify. remove deg 2 nodes when possible. group by oneway and highway to merge each links.
    links = simplify(links)

    # split onwway into 2 links a-b, b-a
    if split_direction:
        links = split_oneway(links)

    # Clean Cul de Sac
    print("Remove Cul de Sac ...")
    links, nodes = main_strongly_connected_component(links, nodes, not split_direction)

    print('removing list in columns ...')
    links['maxspeed'] = links['maxspeed'].apply(lambda x: process_list_in_col(x, float, np.nanmean))
    links['lanes'] = links['lanes'].apply(lambda x: process_list_in_col(x, float, lambda x: np.floor(np.nanmean(x))))
    if 'cycleway' in links.columns:
        # sort and take last. sorted = [no,shared,yes]. so yes or shared if there is a list
        links['cycleway'] = links['cycleway'].apply(lambda x: process_list_in_col(x,str,lambda x: np.sort(x)[-1]))
        links['cycleway_reverse'] = links['cycleway_reverse'].apply(lambda x: process_list_in_col(x,str,lambda x: np.sort(x)[-1]))

    for col in ['highway','name','surface']:
        links[col] = links[col].apply(lambda x: remove_list_in_col(x,'first'))


    # Fill NaN with mean values by highway
    links = fill_na_col(links, 'highway', 'maxspeed', np.mean)
    links = fill_na_col(links, 'highway', 'lanes', lambda x: np.floor(np.mean(x)))

    # Add length
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
    
    return links, nodes

def handler(event, context):
    '''
    event keys :
    bbox : list[float]
    elevation: bool
    highway : list[str]
    callID : str

    '''
    print(event)
    bucket_name = os.environ['BUCKET_NAME']
    wd = '/tmp/'
    # add elevation arg. if not provided. set to True
    if 'elevation' in (event.keys()):
        add_elevation = event['elevation']
    else:
        add_elevation = True

    if 'splitDirection' in (event.keys()):
        split_direction = event['splitDirection']
    else:
        split_direction = False

    # get bbox and requested highway
    bbox = event['bbox']
    bbox = (*bbox,) # list to tuple
    highway_list = event['highway']
    cycleway_list = None
    if "cycleway" in highway_list:
        cycleway_list = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                        "share_busway", "opposite_share_busway", "shared_lane"]

    links, nodes = osm_importer(bbox, highway_list, cycleway_list, wd)
    links, nodes = osm_simplify(links, nodes, highway_list, add_elevation, split_direction)
    
    # Outputs
    print('Saving on S3')
    folder = event['callID']
    links.to_file(f's3://{bucket_name}/{folder}/links.geojson', driver='GeoJSON')
    nodes.to_file(f's3://{bucket_name}/{folder}/nodes.geojson', driver='GeoJSON')
    print('Success!')
    #links.to_file(os.path.join(wd, 'links.geojson'))
    #nodes.to_file(os.path.join(wd, 'nodes.geojson'))
