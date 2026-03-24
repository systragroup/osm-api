import sys
import unittest
import os
from shapely.geometry import LineString

sys.path.insert(0, r'../osm-api/')
from osm_importer.overpass import get_overpass_query, get_overpass_data, ways_to_geojson, get_bbox, add_tags_as_columns

from common import BBOX, HIGHWAY_LIST, HIGHWAY_COLUMNS, CYCLEWAY_LIST, CYCLEWAY_COLUMNS, to_json, read_json, get_path


SKIP = False
data_path = get_path()


@unittest.skipIf(SKIP, 'want to skip')
class TestFetch(unittest.TestCase):
	@classmethod
	def setUpClass(self):

		# import roads
		overpass_query = get_overpass_query(BBOX, 'highway', HIGHWAY_LIST)
		rlinks_data = get_overpass_data(overpass_query)
		to_json(rlinks_data, os.path.join(data_path, 'rlinks_data.json'))

		# import raod and cycleways
		cycleway_query = get_overpass_query(BBOX, 'cycleway', CYCLEWAY_LIST)
		query = overpass_query + cycleway_query

		cycleways_data = get_overpass_data(query)
		to_json(cycleways_data, os.path.join(data_path, 'cycleways_data.json'))

	def test_get_bbox(self):
		poly = [[-74.021412, 40.696947], [-73.998055, 40.7603484], [-74.021472, 40.696069]]
		bbox = get_bbox(poly)
		self.assertEqual(bbox, (40.696069, -74.021472, 40.7603484, -73.998055))

	def test_ways_to_geojson(self):
		ways = read_json(os.path.join(data_path, 'rlinks_data.json'))
		df = ways_to_geojson(ways, geometry=LineString)
		self.assertTrue(len(df) > 0)

	def test_add_tags_as_columns(self):
		ways = read_json(os.path.join(data_path, 'rlinks_data.json'))
		df = ways_to_geojson(ways, geometry=LineString)
		rlinks = add_tags_as_columns(df, tags=HIGHWAY_COLUMNS)
		self.assertTrue(all([col in rlinks.columns for col in HIGHWAY_COLUMNS]))
		rlinks.to_file(os.path.join(data_path, 'rlinks.geojson'))

	def test_add_tags_as_columns2(self):
		ways = read_json(os.path.join(data_path, 'cycleways_data.json'))
		df = ways_to_geojson(ways, geometry=LineString)
		tags = [*HIGHWAY_COLUMNS, *CYCLEWAY_COLUMNS]
		rlinks = add_tags_as_columns(df, tags=tags)
		self.assertTrue(all([col in rlinks.columns for col in tags]))
		rlinks.to_file(os.path.join(data_path, 'cycleways.geojson'))


if __name__ == '__main__':
	if not os.path.exists('tmp'):
		os.makedirs('tmp')
	unittest.main()
