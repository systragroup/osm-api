# from home
# python tests/test_osm.py
import unittest
import os
import numpy as np
import geopandas as gpd
import pandas as pd

from osm_importer import road

from common import get_path, HIGHWAY_COLUMNS, CYCLEWAY_COLUMNS

data_path = get_path()
SKIP = False


@unittest.skipIf(SKIP, 'want to skip')
class SimpleTests(unittest.TestCase):
	def test_process_list_in_col(self):
		res = road.process_list_in_col([2, 3], float, np.nanmean)
		self.assertEqual(res, 2.5)
		res = road.process_list_in_col([2, np.nan], float, np.nanmean)
		self.assertEqual(res, 2.0)
		res = road.process_list_in_col([1, 2, 3], float, np.sum)
		self.assertEqual(res, 6.0)
		res = road.process_list_in_col(5, float, np.nanmean)
		self.assertEqual(res, 5)
		res = road.process_list_in_col(5, str, np.nanmean)
		self.assertEqual(res, '5')

	def test_remove_list_in_col(self):
		res = road.remove_list_in_col([1, 2, 3, 4, 5], 'first')
		self.assertEqual(res, 1)
		res = road.remove_list_in_col([1, 2, 3, 4, 5], 'last')
		self.assertEqual(res, 5)
		res = road.remove_list_in_col(4, 'first')
		self.assertEqual(res, 4)

	def test_get_epsg(self):
		res = road.get_epsg(45.5, -73.5)
		self.assertTrue(res, 32618)
		res = road.get_epsg(48.8, 2.34)
		self.assertTrue(res, 32631)


@unittest.skipIf(SKIP, 'want to skip')
class TestRead(unittest.TestCase):
	def test_get_links_and_nodes(self):
		ways = gpd.read_file(os.path.join(data_path, 'rlinks.geojson'))
		links, nodes = road.get_links_and_nodes(ways)
		for tag in HIGHWAY_COLUMNS:
			self.assertTrue(tag in links.columns)
		self.assertTrue(links.crs == 4326)
		self.assertTrue(links.crs == nodes.crs)
		self.assertTrue(len(links) > 0)
		self.assertEqual(links.index[0], 0)
		self.assertEqual(links.index[-1], len(links) - 1)
		self.assertEqual(nodes.index[0], 0)

	def test_get_links_and_nodes_with_cycleway(self):
		ways = gpd.read_file(os.path.join(data_path, 'cycleways.geojson'))
		links, nodes = road.get_links_and_nodes(ways)
		for tag in [*HIGHWAY_COLUMNS, *CYCLEWAY_COLUMNS]:
			self.assertTrue(tag in links.columns)
		self.assertTrue(links.crs == 4326)
		self.assertTrue(links.crs == nodes.crs)
		self.assertTrue(len(links) > 0)
		self.assertEqual(links.index[0], 0)
		self.assertEqual(links.index[-1], len(links) - 1)
		self.assertEqual(nodes.index[0], 0)


@unittest.skipIf(SKIP, 'want to skip')
class TestCleaning(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		ways = gpd.read_file(os.path.join(data_path, 'rlinks.geojson')).set_index('id')
		links, nodes = road.get_links_and_nodes(ways)
		self.links = links
		self.nodes = nodes

	def test_clean_oneway(self):
		links = road.clean_oneway(self.links)
		self.assertSetEqual(set(links['oneway'].unique()), set([True, False]))

	def test_clean_maxspeed(self):
		links = road.clean_maxspeed(self.links)
		self.assertTrue(all([isinstance(val, np.float64) for val in links['maxspeed'].unique()]))

	def test_drop_duplicated_links(self):
		test_df = pd.DataFrame(
			[
				{'a': 'node_1', 'b': 'node_2', 'speed': 100},
				{'a': 'node_1', 'b': 'node_2', 'speed': 130},
				{'a': 'node_1', 'b': 'node_2', 'speed': 10},
				{'a': 'node_3', 'b': 'node_4', 'speed': 10},
			]
		)
		res_df = pd.DataFrame(
			[{'a': 'node_1', 'b': 'node_2', 'speed': 130}, {'a': 'node_3', 'b': 'node_4', 'speed': 10}]
		)
		test_df = road.drop_duplicated_links(test_df, sort_column='speed')
		pd.testing.assert_frame_equal(test_df.reset_index(drop=True), res_df)


@unittest.skipIf(SKIP, 'want to skip')
class TestSimplify(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		ways = gpd.read_file(os.path.join(data_path, 'rlinks.geojson'))
		links, nodes = road.get_links_and_nodes(ways)
		links = road.clean_oneway(links)
		links = road.clean_maxspeed(links)
		links = road.drop_duplicated_links(links, sort_column='maxspeed')

		self.links = links
		self.nodes = nodes

	def test_simplify(self):
		length = len(self.links)
		links = road.simplify(self.links)
		# should contain list as we merge.
		self.assertTrue(any([isinstance(val, list) for val in links['osmid'].values]))
		# should have less links
		self.assertGreater(length, len(links))

	def test_simplify_index_string(self):
		links_string = self.links.copy()
		links_string.index = 'rlink_' + links_string.index.astype(str)
		A = road.simplify(self.links)
		B = road.simplify(links_string)
		# should have the samne result (except for index )
		pd.testing.assert_frame_equal(A.reset_index(drop=True), B.reset_index(drop=True))

	def test_split_oneway(self):
		expected_length = len(self.links) + len(self.links[~self.links['oneway']])
		links = road.split_oneway(self.links)
		# should add the correct number of links.
		self.assertEqual(len(links), expected_length)

	def test_main_strongly_connected_component(self):
		links = road.simplify(self.links)
		links = road.split_oneway(links)
		length = len(links)
		links = road.main_strongly_connected_component(links, None, False)
		# should remove links
		self.assertGreater(length, len(links))

		# should remove all links in this case.
		test = road.main_strongly_connected_component(links.iloc[0:2], None, False)
		self.assertTrue(len(test) == 0)


@unittest.skipIf(SKIP, 'want to skip')
class TestListCleaning(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		ways = gpd.read_file(os.path.join(data_path, 'rlinks.geojson'))
		links, nodes = road.get_links_and_nodes(ways)
		links = road.clean_oneway(links)
		links = road.clean_maxspeed(links)
		links = road.drop_duplicated_links(links, sort_column='maxspeed')
		links = road.simplify(links)
		links = road.split_oneway(links)
		links = road.main_strongly_connected_component(links, None, False)
		self.links = links
		self.nodes = nodes

	def test_fill_na_col(self):
		links = self.links
		links['maxspeed'] = links['maxspeed'].apply(lambda x: road.process_list_in_col(x, float, np.nanmean))
		links = road.fill_na_col(links, 'highway', 'maxspeed', np.mean)
		self.assertTrue(all([np.isfinite(val) for val in links['maxspeed'].unique()]))


if __name__ == '__main__':
	if not os.path.exists('tmp'):
		os.makedirs('tmp')
	unittest.main()
