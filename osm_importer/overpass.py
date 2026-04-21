import requests
import pandas as pd
import geopandas as gpd
import time
from shapely import geometry
from typing import TypeAlias, Optional
import logging

log = logging.getLogger(__name__)
BBOX: TypeAlias = tuple[float, float, float, float]
OVERPASS_URL = 'http://overpass-api.de/api/interpreter'
HEADERS = {'User-Agent': 'osm-api python (https://github.com/systragroup/osm-api)'}


def _overpass_decorator(query: str):
	"""
	take a overpass proto query get_overpass_query() and add headers and footer
	"""
	header = """
	[out:json][timeout:180];
	(
	"""
	footer = """ 
	);
	out body;
	>;
	out skel qt;
	"""
	return header + query + footer


def get_overpass_query(bbox: BBOX, key: str = 'highway', tag_list: list[str] = []) -> str:
	"""
	bbox : (ymin, xmin, ymax, xmax)
	key: osm key ex:highway will fetch way[highway]
	# tag_list: list of tag to includes ex: way[highway ~ motorway | primary]. if empty import all
	"""
	if len(tag_list) == 0:
		return f'way["{key}"]{bbox};\n'
	else:
		tags = '|'.join([tag for tag in tag_list])
		return f'way["{key}"~"{tags}"]{bbox};\n'


def get_overpass_data(query: str, retries: int = 3) -> dict:

	overpassQuery = _overpass_decorator(query)
	for i in range(1, retries + 1):
		try:
			response = requests.get(OVERPASS_URL, params={'data': overpassQuery}, headers=HEADERS, timeout=60)
			if response.status_code != 200:
				raise Exception(f'Overpass API error {response.status_code}: {response.text[:200]}')

			return response.json()
		except Exception as err:
			log.info(err)
			if i < retries:
				wait = 2**i
				log.info(f'retrying in {wait} seconds')
				time.sleep(wait)
	raise Exception('Could not import data from Overpass API. try again')


# transform


def ways_to_geojson(data: dict, geometry: geometry = geometry.LineString) -> gpd.GeoDataFrame:
	"""
	data: osm fetched data object
	geometry: function: how to create geometry from nodes.
	"""
	ways = pd.DataFrame([d for d in data['elements'] if d['type'] == 'way']).set_index('id')
	nodes = pd.DataFrame([d for d in data['elements'] if d['type'] == 'node']).set_index('id')
	# Convert elements to GeoPandas
	way_exploded = ways.explode('nodes').merge(nodes[['lat', 'lon']], left_on='nodes', right_index=True, how='left')
	geom = way_exploded.groupby('id')[['lon', 'lat']].apply(lambda x: geometry(x.values))
	geom.name = 'geometry'
	ways = gpd.GeoDataFrame(ways.join(geom), crs=4326)

	return ways


def add_tags_as_columns(
	ways: gpd.GeoDataFrame, tags: Optional[list[str]] = None, to_drop: list[str] = ['nodes', 'type']
):
	"""
	create new column with tags key. if None. use all tags
	"""
	tags_df = pd.DataFrame.from_records(ways['tags'].values, index=ways['tags'].index)
	if tags is None:
		cols = tags_df.columns
	else:
		cols = [col for col in tags if col in tags_df.columns]
	ways = ways.drop(columns=to_drop, errors='ignore').join(tags_df[cols])
	return ways.reset_index()


def import_data_from_osm(bbox: BBOX, key: str, geometry: geometry, tag_list: list[str] = []) -> gpd.GeoDataFrame:
	overpassQuery = get_overpass_query(bbox, key, tag_list)
	data = get_overpass_data(overpassQuery)
	ways = ways_to_geojson(data, geometry)
	ways = add_tags_as_columns(ways, tags=[key])
	return ways


def get_bbox(ls: list[list[float]]) -> tuple[float, float, float, float]:
	"""
	from a list of coords [[lon, lat], [lon, lat]], ...] get bbox around

	parameters
	----------
	ls: list of coords

	returns
	----------
	tuple (lat_min, lon_min, lat_max, lon_max)
	"""
	xmin = min([coord[0] for coord in ls])
	xmax = max([coord[0] for coord in ls])
	ymin = min([coord[1] for coord in ls])
	ymax = max([coord[1] for coord in ls])
	return (ymin, xmin, ymax, xmax)
