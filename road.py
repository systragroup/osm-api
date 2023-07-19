import json
from copy import deepcopy
import geopandas as gpd
from  shapely.ops import transform
from shapely.geometry import MultiLineString, Point
from shapely.ops import linemerge
import numpy as np
import pandas as pd
import networkx as nx
from itertools import islice
from scipy.sparse.csgraph import dijkstra
from scipy.sparse import csr_matrix
from numba import jit
import numba as nb
from typing import *


def process_list_in_col(col_values: Any, new_type : Any ,function: Callable[[Any],Any] = np.nanmean) -> Any:
        '''
        ex: links['maxspeed'].apply(lambda x: process_list_in_col(x,float,np.nanmean)
        apply the function to the list. if its not a list. apply new type.
        '''
        if isinstance(col_values, list):
            return  function([new_type(val) for val in col_values])
        else:
            return new_type(col_values)
        
def remove_list_in_col(col_values: Any, method: str ='first'):
    '''
    remove list. keep first item if first, last if last. return any other value that are not a list
    '''
    if isinstance(col_values, list):
        if method == 'first':
            return col_values[0]
        else:
            return col_values[-1]
    else:
        return col_values
    
def get_epsg(lat: float, lon: float) -> int:
    '''
    return EPSG in meter for a given (lat,lon)
    lat is north south 
    lon is est west
    '''
      
    return int(32700 - round((45 + lat) / 90, 0) * 100 + round((183 + lon) / 6, 0))

# buildindex
def build_index(edges):
    nodelist = {e[0] for e in edges}.union({e[1] for e in edges})
    nlen = len(nodelist)
    return dict(zip(nodelist, range(nlen)))

def sparse_matrix(edges, index=None):
    if index is None:
        index = build_index(edges)
    nlen = len(index)
    coefficients = zip(*((index[u], index[v], w) for u, v, w in edges))
    row, col, data = coefficients
    return csr_matrix((data, (row, col)), shape=(nlen, nlen)), index

@jit(nopython=True,locals={'predecessors':nb.int32[:,::1],'i':nb.int32,'j':nb.int32})
def get_path(predecessors, i, j):
    path = [j]
    k = j
    p = 0
    while p != -9999:
        k = p = predecessors[i, k]
        path.append(p)
    return path[::-1][1:]

def get_edge_path(p):
    return list(zip(p[:-1], p[1:]))

def merged_reversed_geometries_dict(geojson_dict):
    features = {
        hash(tuple(tuple(p) for p in feature['geometry']['coordinates'])):
        feature for feature in geojson_dict['features']
    }
    counts = {}  # {geohash : 2 if the reverse geohash is in the geometries, 1 otherwise}
    drop = set()  # for each direct/indirect geometry pair, countain the lesser geohash
    for _, feature in features.items():
        geo_tuple = tuple(tuple(p) for p in feature['geometry']['coordinates'])
        reversed_geo_tuple = reversed(geo_tuple)
        k = hash(tuple(geo_tuple))
        kr = hash(tuple(reversed_geo_tuple))
        drop.add(min(k, kr))
        counts[k] = counts.get(k, 0) + 1
        counts[kr] = counts.get(kr, 0) + 1
        if k == kr:
            print('hey')

    # keep only the feature with the higher geohash
    drop = {d for d in drop if counts[d] > 1}
    features = {k: v for k, v in features.items() if k not in drop}
    for k, v in features.items():
        v['properties']['oneway'] = int(counts[k] == 1)

    result = dict(geojson_dict)
    result['features'] = list(features.values())
    return result


def merge_reversed_geometries(geometries):
    try:
        return merged_reversed_geometries_dict(geometries)
    except KeyError:  # 'features'
        geojson_dict = json.loads(geometries.to_json())
        temp = merged_reversed_geometries_dict(geojson_dict)
        return gpd.read_file(json.dumps(temp))


def get_intersections(geojson_dict):
    count = {}
    for feature in geojson_dict['features']:
        for p in feature['geometry']['coordinates']:
            count[tuple(p)] = count.get(tuple(p), 0) + 1
    return {k for k, v in count.items() if v > 1}


def get_nodes(geojson_dict):
    nodes = set()
    for feature in geojson_dict['features']:
        nodes.add(tuple(feature['geometry']['coordinates'][0]))
        nodes.add(tuple(feature['geometry']['coordinates'][-1]))
    return nodes.union(get_intersections(geojson_dict))


def split_feature(feature, nodes=(), start=0):
    length = len(feature['geometry']['coordinates'])
    if length == 2:
        return [feature]
    if length > 2:
        cut = 0
        for p in feature['geometry']['coordinates'][start + 1: length - 1]:
            
            cut += 1
            if tuple(p) in nodes:
                left = deepcopy(feature)
                right = deepcopy(feature)
                left['geometry']['coordinates'] = left['geometry']['coordinates'][start: cut + 1]
                right['geometry']['coordinates'] = right['geometry']['coordinates'][cut:]
                return [left] + split_feature(right, nodes=nodes, start=0)
    return [feature]


def get_split_features(geojson_dict):
    features = []
    intersections = get_intersections(geojson_dict)
    for feature in geojson_dict['features']:
        features += split_feature(feature, nodes=intersections) 
    return features


def split_features(geojson_dict):
    geojson_dict['features'] = get_split_features(geojson_dict)

def split_directions(geojson_dict):
    features = geojson_dict['features']
    reversed_features = [deepcopy(f) for f in features if not f['properties']['oneway']]
    for f in reversed_features:
        f['geometry']['coordinates'] = list(reversed(f['geometry']['coordinates']))
    geojson_dict['features'] = features + reversed_features

def get_links_and_nodes(geojson_file: str, split_direction: bool = False) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    '''
    read overpass way.geojson file and return links and nodes as gpd.GeoDataFrames.
    Split direction dangerous here as Oneway tag is still rough (not just true / false...)

    parameters
    ----------
    geojson_file (str) : path of the file
    split_direction (bool) : if we want to duplicate oneway=False and reverse the geom.

    returns
    ----------
    links, nodes
    '''
    with open(geojson_file, 'r') as file:
        text = file.read()
    
    road =  json.loads(text)
    split_features(road)
    
    node_coordinates = list(get_nodes(road))
    node_index = dict(
        zip(
            node_coordinates, 
            ['road_node_%i' % i for i in range(len(node_coordinates))]
        )
    )
    df = pd.DataFrame(node_index.items(), columns=['coordinates', 'index'])
    df['geometry'] = df['coordinates'].apply(lambda t: Point(t))
    nodes = gpd.GeoDataFrame(df.set_index(['index'])[['geometry']])

    if split_direction:
        split_directions(road)

    for f in road['features']:
        first = tuple(f['geometry']['coordinates'][0])
        last = tuple(f['geometry']['coordinates'][-1])
        f['properties']['a'] = node_index[first]
        f['properties']['b'] = node_index[last]

    links = gpd.read_file(json.dumps(road))
    links.index = ['road_link_%i' % i for i in range(len(links))]
    links = links.drop(columns=['id','type'])
    return links, nodes

def main_strongly_connected_component(links: gpd.GeoDataFrame,
                                       nodes: gpd.GeoDataFrame = None, 
                                       split_direction: bool = False) -> gpd.GeoDataFrame:
    '''
    use split direction if the links are not duplicated (if there is 1 link for oneway=False)
    remove cul-de-sac
    '''
    graph = nx.DiGraph()
    graph.add_edges_from(links[['a', 'b']].values.tolist())
    if 'oneway' in links.columns and split_direction :
        graph.add_edges_from(
            links.loc[~links['oneway'].astype(bool)][['b', 'a']].values.tolist()
        )

    main_scc = None
    size = 0
    for scc in nx.strongly_connected_components(graph):
        if len(scc) > size :
            size = len(scc)
            main_scc = scc

    l = links.loc[links['a'].isin(main_scc) & links['b'].isin(main_scc)]
    if nodes is not None:
        n = nodes.loc[list(main_scc)]
        return l, n
    return l 

def reverse_geom(geom):
    def _reverse(x, y, z=None):
        if z:
            return x[::-1], y[::-1], z[::-1]
        return x[::-1], y[::-1]
    return transform(_reverse, geom)

def rectify_geometry_direction(links,nodes):
    
    node_dict = nodes['geometry'].to_dict()
    links['node_geom'] = links['a'].apply(lambda x: node_dict.get(x))
    sliced = links['geometry'].apply(lambda x: x.coords[0]) != links['node_geom'].apply(lambda x: x.coords[0])
    print(len(links[sliced]),'geometry to inverse')
    links.loc[sliced,'geometry'] = links.loc[sliced]['geometry'].apply(lambda x: reverse_geom(x))
    links = links.drop(columns = 'node_geom')
    return links

def batched(iterable, n):
    "Batch data into lists of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch

def simplify(links,cutoff = 10):
    #create a graph and find all nodes with deg >2 (sources)
    G = nx.DiGraph()
    G.add_edges_from(links[['a', 'b']].values.tolist())
    sources = [node for node,degree in dict(G.degree()).items() if degree > 2]
    deg_dict = dict(G.degree())
    links['weight']=1
    print(len(sources),'deg 2 nodes')
    path_to_merge = []
    # graph on oneway and highway as unique as we dont want to aggregate highway together or one way 
    for col1, col2 in [(a,b) for a in links['oneway'].unique() for b in links['highway'].unique()]:
        filtered_links = links[(links['oneway']==col1) & (links['highway']==col2)]
        if len(filtered_links) < 2:
            continue
        nodes_set = set(filtered_links['a']).union(set(filtered_links['b']))
        mat, node_index = sparse_matrix(filtered_links[['a', 'b', 'weight']].values)
        sparse_deg_dict = {node_index[key]:val for key,val in deg_dict.items() if key in nodes_set}
        index_node = {v: k for k, v in node_index.items()}
        filtered_sources  = [s for s in sources if s in nodes_set]
        unfounds_origins = []
        
        # 1) for each nodes with deg > 2
        # 2) take all non empty path
        # 3) take all path with destination a node with deg > 2
        #    and only deg 2 nodes in between ex: [3,2,2,4]
        # 4) take all path with destination a node of deg == 2
        #    if the path length is the cutoff.

        
        # batch the dijkstra, my computer was crashing with ~40 000 sources
        # it it not that much slower.
        for origins in batched(filtered_sources,1000):
            origin_sparse = [node_index[x] for x in origins]
            dist_matrix,predecessors = dijkstra(
                    csgraph=mat,
                    directed=True,
                    indices=origin_sparse,
                    return_predecessors=True,
                    limit=cutoff
                )

            #from all source (source are deg>2 by construction)
            for oi in range(len(origins)):
                # destinations are non inf paths
                destinations = np.where(dist_matrix[oi,:]!=np.inf)[0]
                # for each destination with deg >= 2
                for di in (d for d in destinations if sparse_deg_dict[d]>=2):
                    path = get_path(predecessors, oi, di) #get path, with origin and destinations in the list
                    path_deg = [*map(sparse_deg_dict.get, path)] #get deg of each nodes in path
                    #if destination is not 2. keep path if every nodes in between are 2
                    if (path_deg[-1]!=2): 
                        if (set(path_deg[1:-1]) == {2}):
                            path_to_merge.append([*map(index_node.get, path)])
                            if len(path_to_merge)>1:
                                if path_to_merge[-1] == path_to_merge[-2]:
                                    print(path)
                    #if destination == 2 
                    elif len(path) == cutoff+1: 
                        #keep path if len(path) == cutoff+1. at the end redo on those with large cutoff
                        if (set(path_deg[1:]) == {2}):
                            unfounds_origins.append(origins[oi])

        # redo with large cutoff the path thats were longer than the cutoff
        # ex:cutoff = 5, path = [3,2,2,2,2]. the real path may be [3,2,2,2,2,2,2,2,4]. and we will find it now.
        if len(unfounds_origins)>0:
            print('find path with large cutoff for', len(unfounds_origins),' origins')
            origin_sparse = [node_index[x] for x in unfounds_origins]
            dist_matrix,predecessors = dijkstra(
                    csgraph=mat,
                    directed=True,
                    indices=origin_sparse,
                    return_predecessors=True,
                    limit=100
                )
            for oi in range(len(unfounds_origins)):
                # destinations are non inf paths
                destinations = np.where(dist_matrix[oi,:]!=np.inf)[0]
                # for each destination with deg >= 2
                for di in (d for d in destinations if sparse_deg_dict[d]>=2):
                    path = get_path(predecessors, oi, di) #get path, with origin and destinations in the list
                    path_deg = [*map(sparse_deg_dict.get, path)] #get deg of each nodes in path
                    #if destination is not 2. keep path if every nodes in between are 2
                    #those were not find in cutoff, only check for larger cutoff.
                    if (path_deg[-1]!=2) &(len(path) >= cutoff+1):  
                        if (set(path_deg[1:-1]) == {2}):
                            path_to_merge.append([*map(index_node.get, path)])

    # transform sparse nodes path to links path ([rlinks_2, rlinks_40, ...])
    links_dict = links.reset_index().set_index(['a','b'])['index'].to_dict()
    links_paths = [[*map(links_dict.get, get_edge_path(path))]for path in path_to_merge]

    #apply a group number to each sequence to merge. group 0 is nothing to merge.
    links['group']=0
    idx=1
    for path in links_paths:
        links.loc[path,'group']=idx
        idx+=1
    tlinks = links[links['group']>0].copy()
    # sort tlinks links to merge in the right order
    flat_index = [l for sublist in links_paths for l in sublist]
    tlinks = tlinks.loc[flat_index]

    #for some reason, it doesnt work when i do it in the next groupby
    index_dict = tlinks.reset_index().groupby('group')['index'].agg('first').to_dict()

    list_or_first = lambda x : list(x) if len(set(x))>1 else x[0]
    merge_lines = lambda x: linemerge(MultiLineString(list(x)))

    # merge links
    agg_dict = {col:list_or_first for col in tlinks.columns}
    agg_dict['geometry']=merge_lines
    agg_dict['a']='first'
    agg_dict['b']='last'
    tlinks = tlinks.groupby('group').agg(agg_dict)
    tlinks.index = tlinks.index.map(index_dict)
    tlinks.index.name=''


    #remove agg that change oneway
    print(len(tlinks[tlinks['oneway'].apply(lambda x: type(x)==list)]),'links were not merge because the oneway field is not the same')
    tlinks = tlinks[~tlinks['oneway'].apply(lambda x: type(x)==list)]

    print(len(tlinks[tlinks['highway'].apply(lambda x: type(x)==list)]),'links were not merge because the highway field is not the same')
    tlinks = tlinks[~tlinks['highway'].apply(lambda x: type(x)==list)]


    # TODO: on a des multiLinestring. il faudrait mieux merger.
    print(len(tlinks[tlinks['geometry'].apply(lambda x: x.type != 'LineString')]),'merged_links unmerged because the geometry became a multilinestring')
    tlinks = tlinks[tlinks['geometry'].apply(lambda x: x.type=='LineString')]

    #merge tlinks back into links
    tlinks = gpd.GeoDataFrame(tlinks,crs=links.crs)
    links = links[~links['group'].isin(tlinks['group'].unique())]
    links = pd.concat([links,tlinks])
    links = links.drop(columns=['weight','group'])

    return links

def split_oneway(links: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    duplicated all links with oneway == False. reverse there geometry, reverse a,b and rename with _r
    '''
    nlinks = links[links['oneway']==False].copy()
    nlinks.index = nlinks.index + '_r'
    nlinks['geometry'] = nlinks['geometry'].apply(lambda x: reverse_geom(x))
    nlinks = nlinks.rename(columns={'a':'b','b':'a'})
    links = pd.concat([links,nlinks])
    links['oneway']=True
    return links

def drop_duplicated_links(links: gpd.GeoDataFrame, sort_column: str = 'maxspeed', ascending: bool = False)-> gpd.GeoDataFrame:
    '''
    drop duplicated links (a,b) with condition sort_column. if maxspeed and ascending=False, keep faster road
    '''
    before = len(links)
    links['dup'] = links['a'] + links['b']
    links = links.sort_values(sort_column, ascending=ascending).drop_duplicates('dup').sort_index()
    links = links.drop(columns='dup')
    print(before - len(links), 'links dropped')
    return links



def clean_maxspeed(links: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    remove kph, remove and convert mph. transport everything to float. NaN if string (ex: walk)
    '''
    links['maxspeed'] = links['maxspeed'].str.lower().str.replace('kph', '')
    try:
        mph_index = links['maxspeed'].astype(str).str.lower().str.contains('mph')
        links.loc[mph_index,'maxspeed'] = links.loc[mph_index,'maxspeed'].str.lower().str.replace('mph','').astype('float')* 1.60934
    except:
        print('fail to convert mph in maxspeed to float ')
    # this remove all strings lefts
    links['maxspeed'] = links['maxspeed'].apply(pd.to_numeric, errors='coerce')
    return links

def clean_oneway(links: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    clean oneways. return True or False
    '''
    links['oneway'].fillna('no', inplace=True)
    links['oneway'] = links['oneway'].replace('yes', True).replace('no', False).replace('-1', False).replace(-1, False).replace('alternating',False).replace('reversible',False)
    if len(links['oneway'].unique())>2:
        print('WARNING: some oneway tags are not defined',links.unique())    
    return links

def clean_lanes(links: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    remove semicolon (ex lanes = 1;2) and average the result (1;2 -> 1.5).
    transform everything to float. NaN if string
    '''
    semicolon_index = links['lanes'].astype(str).str.contains(';')
    links.loc[semicolon_index,'lanes'] = links.loc[semicolon_index,'lanes'].apply(lambda x: np.mean([float(el) for el in x.split(';')]))
    links['lanes'] = links['lanes'].apply(pd.to_numeric, errors='coerce')
    return links



def fill_na_col(links: gpd.GeoDataFrame, 
               group: str = 'highway', 
               col: str = 'maxspeed',
               agg_func: Callable[[list],Any] = np.mean) -> gpd.GeoDataFrame:
    '''
    fill the nan value with the average of its group (if np.mean)
    for example: with group=highway, col=maxspeed and agg_func = np.mean. the mean maxpeed per highway is compute.
    then its apply to every NaN value of each highway.
    Note that a group with only NaN will stay a nan (no agg_func will be applied.)

    parameters
    ----------
    links: gpd.GeoDataFrame = links to apply the function
    group: group to do the groupby and find the average (or any other function)
    col: column to fill
    agg_func : function to apply

    returns
    ----------
    {index: elevation} : Dict[Any,int] = elevataion for each index in the GeoDataFrame
    '''
    
    val_dict = links[[group,col]].dropna().groupby(group)[col].agg(agg_func).to_dict()
    links.loc[~np.isfinite(links[col]),col] = links.loc[~np.isfinite(links[col]),group].apply(lambda x: val_dict.get(x))
    return links


def get_columns_with_list(df: pd.DataFrame) -> list:
    '''
    return the list of column that contain list in them.
    '''
    
    def _contain_list(df,col):
        for val in df[col].values:
            if type(val)==list:
                return True
        else:
            return False
    
    object_columns = df.columns[(df.dtypes==object).values]
    res=[]
    for col in object_columns:
        if _contain_list(df,col):
            res.append(col)
    return res