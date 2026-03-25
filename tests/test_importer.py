# from home
# python tests/test_osm.py
import unittest
import os

from osm_importer.importer import import_road_network, simplify_bicycle_network, simplify_road_network

COLS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']
BBOX = (45.516012863655845, -73.61165474010419, 45.54058887207495, -73.56153948806578)
HIGHWAY_LIST = [
	'motorway',
	'motorway_link',
	'trunk',
	'trunk_link',
	'primary',
	'primary_link',
	'secondary',
	'secondary_link',
	'tertiary',
	'tertiary_link',
	'residential',
]
CYCLEWAY_COL = ['cycleway', 'cycleway:both', 'cycleway:left', 'cycleway:right']
CYCLEWAY_LIST = [
	'lane',
	'opposite',
	'opposite_lane',
	'track',
	'opposite_track',
	'share_busway',
	'opposite_share_busway',
	'shared_lane',
]
TAGS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']
CYCLEWAY_COLUMNS = ['cycleway', 'cycleway:both', 'cycleway:left', 'cycleway:right']


POLY = [
	[-74.0204, 40.6961],
	[-74.0110, 40.7506],
	[-73.9673, 40.7444],
	[-73.9671, 40.7296],
	[-73.9745, 40.70946],
	[-73.9941, 40.7067],
	[-74.0204, 40.6961],
]


wd = 'tmp/'

SKIP = False


@unittest.skipIf(SKIP, 'want to skip')
class TestCyclewayImporter(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		self.links, self.nodes = import_road_network(
			bbox=BBOX,
			highway_list=[*HIGHWAY_LIST, 'cycleway'],
			cycleway_list=CYCLEWAY_LIST,
			tags=[*TAGS, *CYCLEWAY_COLUMNS],
		)

		self.elinks, self.enodes = import_road_network(
			bbox=BBOX, highway_list=[*HIGHWAY_LIST, 'cycleway'], cycleway_list=[], tags=[*TAGS, 'cycleway']
		)

	def test_osm_simplify_1(self):
		add_elevation = True
		split_direction = False

		extended_cycleway = False
		keep_detour = False
		links = self.links.copy()
		nodes = self.nodes.copy()
		print(links.columns)
		links = simplify_bicycle_network(links, HIGHWAY_LIST, extended_cycleway=extended_cycleway)
		print(links.columns)
		links, nodes = simplify_road_network(links, nodes, add_elevation, split_direction, keep_detour)

		expected_res = [
			'highway',
			'speed',
			'lanes',
			'name',
			'oneway',
			'surface',
			'cycleway',
			'a',
			'b',
			'geometry',
			'cycleway_reverse',
			'length',
			'time',
			'incline',
		]
		self.assertSetEqual(set(links.columns), set(expected_res))
		self.assertSetEqual(set(nodes.columns), set(['geometry', 'elevation']))
		self.assertTrue(True in links['oneway'].unique())

	def test_osm_simplify_2(self):
		add_elevation = False
		split_direction = True

		extended_cycleway = False
		keep_detour = False
		links = self.links.copy()
		nodes = self.nodes.copy()
		links = simplify_bicycle_network(links, HIGHWAY_LIST, extended_cycleway=extended_cycleway)
		links, nodes = simplify_road_network(links, nodes, add_elevation, split_direction, keep_detour)
		expected_res = [
			'highway',
			'speed',
			'lanes',
			'name',
			'oneway',
			'surface',
			'cycleway',
			'a',
			'b',
			'geometry',
			'cycleway_reverse',
			'length',
			'time',
		]

		self.assertSetEqual(set(links['cycleway'].unique()), set(['no', 'yes', 'shared']))
		self.assertSetEqual(set(links.columns), set(expected_res))
		self.assertSetEqual(set(nodes.columns), set(['geometry']))
		self.assertTrue(False not in links['oneway'].unique())

	def test_osm_simplify_4(self):
		add_elevation = True
		split_direction = False
		extended_cycleway = True

		extended_cycleway = True
		keep_detour = False
		links = self.elinks.copy()
		nodes = self.enodes.copy()
		links = simplify_bicycle_network(links, HIGHWAY_LIST, extended_cycleway=extended_cycleway)
		links, nodes = simplify_road_network(links, nodes, add_elevation, split_direction, keep_detour)
		expected_res = [
			'highway',
			'speed',
			'lanes',
			'name',
			'oneway',
			'surface',
			'cycleway',
			'a',
			'b',
			'geometry',
			'cycleway_reverse',
			'length',
			'time',
			'incline',
		]
		self.assertSetEqual(set(links.columns), set(expected_res))
		self.assertSetEqual(set(nodes.columns), set(['geometry', 'elevation']))

		self.assertTrue(True in links['oneway'].unique())


@unittest.skipIf(SKIP, 'want to skip')
class TestHighwayImporter(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		self.links, self.nodes = import_road_network(bbox=BBOX, highway_list=HIGHWAY_LIST, tags=TAGS)

	def test_osm_simplify_1(self):
		add_elevation = True
		split_direction = False
		links = self.links.copy()
		nodes = self.nodes.copy()
		links2 = self.links.copy()
		nodes2 = self.nodes.copy()
		links, nodes = simplify_road_network(links, nodes, add_elevation, split_direction, False)
		links2, nodes2 = simplify_road_network(links2, nodes2, add_elevation, split_direction, True)

		expected_res = [
			'highway',
			'speed',
			'lanes',
			'name',
			'oneway',
			'surface',
			'a',
			'b',
			'geometry',
			'length',
			'time',
			'incline',
		]
		self.assertSetEqual(set(links.columns), set(expected_res))
		self.assertSetEqual(set(nodes.columns), set(['geometry', 'elevation']))
		self.assertTrue(True in links['oneway'].unique())
		self.assertTrue(len(links2) >= len(links))

	def test_osm_simplify_2(self):
		add_elevation = False
		split_direction = True
		links = self.links.copy()
		nodes = self.nodes.copy()
		links, nodes = simplify_road_network(links, nodes, add_elevation, split_direction, False)

		expected_res = [
			'highway',
			'speed',
			'lanes',
			'name',
			'oneway',
			'surface',
			'a',
			'b',
			'geometry',
			'length',
			'time',
		]
		self.assertSetEqual(set(links.columns), set(expected_res))
		self.assertSetEqual(set(nodes.columns), set(['geometry']))
		self.assertTrue(True in links['oneway'].unique())


if __name__ == '__main__':
	if not os.path.exists('tmp'):
		os.makedirs('tmp')
	unittest.main()
