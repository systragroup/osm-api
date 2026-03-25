import numpy as np
import logging
from osm_importer.road import (
	clean_oneway,
	clean_maxspeed,
	clean_lanes,
	rectify_geometry_direction,
	drop_duplicated_links,
	simplify,
	split_oneway,
	main_strongly_connected_component,
	process_list_in_col,
	remove_list_in_col,
	fill_na_col,
	get_epsg,
	split_duplicated_links,
)
from osm_importer.bike import test_bicycle_process, extended_bicycle_process
from osm_importer.elevation import get_elevation_from_srtm, calc_incline
import geopandas as gpd

log = logging.getLogger(__name__)

CYCLEWAY_COLUMNS = ['cycleway:both', 'cycleway:left', 'cycleway:right']
HIGHWAY_COLUMNS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']


def road_network_simplify(
	links: gpd.GeoDataFrame,
	nodes: gpd.GeoDataFrame,
	highway_list: list[str],
	add_elevation: bool = True,
	split_direction: bool = False,
	extended_cycleway: bool = False,
	keep_detour: bool = False,
):

	# simplify Linestring geometry. (remove anchor nodes)
	links.geometry = links.simplify(0.00005)

	if 'cycleway' in links.columns:
		if extended_cycleway:
			links = extended_bicycle_process(links)
		else:
			links = test_bicycle_process(links, CYCLEWAY_COLUMNS, highway_list)

	links = links.drop(columns='tags', errors='ignore')
	# convert oneway to bool.
	links = clean_oneway(links)

	# remove string in maxspeed
	links = clean_maxspeed(links)

	# remove string in maxspeed
	links = clean_lanes(links)

	# make sure the geometry are in the right direction (a->b)
	links = rectify_geometry_direction(links, nodes)

	# remove duplicated links (a-b)
	log.info('simplifying links ...')
	if keep_detour:
		links, nodes = split_duplicated_links(links, nodes)
	else:
		links = drop_duplicated_links(links)

	# simplify. remove deg 2 nodes when possible. group by oneway and highway to merge each links.
	links = simplify(links)

	# split onwway into 2 links a-b, b-a
	if split_direction:
		links = split_oneway(links)

	# Clean Cul de Sac
	log.info('Remove Cul de Sac ...')
	links, nodes = main_strongly_connected_component(links, nodes, not split_direction)

	log.info('removing list in columns ...')
	links['maxspeed'] = links['maxspeed'].apply(lambda x: process_list_in_col(x, float, np.nanmean))
	links['lanes'] = links['lanes'].apply(lambda x: process_list_in_col(x, float, lambda x: np.floor(np.nanmean(x))))
	if 'cycleway' in links.columns:
		# sort and take last. sorted = [no,shared,yes]. so yes or shared if there is a list
		links['cycleway'] = links['cycleway'].apply(lambda x: process_list_in_col(x, str, lambda x: np.sort(x)[-1]))
		links['cycleway_reverse'] = links['cycleway_reverse'].apply(
			lambda x: process_list_in_col(x, str, lambda x: np.sort(x)[-1])
		)

	for col in ['highway', 'name', 'surface']:
		links[col] = links[col].apply(lambda x: remove_list_in_col(x, 'first'))

	# Fill NaN with mean values by highway
	links = fill_na_col(links, 'highway', 'maxspeed', lambda x: np.mean(x))
	links = fill_na_col(links, 'highway', 'lanes', lambda x: np.floor(np.mean(x)))

	# Add length
	epsg = get_epsg(nodes.iloc[0]['geometry'].y, nodes.iloc[0]['geometry'].x)
	links['length'] = links.to_crs(epsg).length

	# Add Time
	links['time'] = links['length'] / (links['maxspeed'] * 1000 / 3600)
	links = links.rename(columns={'maxspeed': 'speed'})

	# reindex and remove ununsed nodes
	links = links.reset_index(drop=True)
	links.index = 'rlink_' + links.index.astype(str)
	nodes_set = set(links['a']).union(set(links['b']))
	nodes = nodes.loc[list(nodes_set)].sort_index()

	if add_elevation:
		log.info('Adding elevation')
		el_dict = get_elevation_from_srtm(nodes)
		nodes['elevation'] = nodes.index.map(el_dict.get)
		# incline from node a to b in deg. neg if going down (if b is lower dans a)
		links['incline'] = calc_incline(
			links['a'].apply(lambda x: el_dict.get(x)).values,
			links['b'].apply(lambda x: el_dict.get(x)).values,
			links['length'].values,
		)

	return links, nodes
