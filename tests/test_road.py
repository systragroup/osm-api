# from home
# python tests/test_osm.py 
import sys
import json
import random
import unittest
from unittest.mock import patch
import os
import pandas as pd
import geopandas as gpd
import numpy as np
sys.path.insert(0, r'../osm-api/')
from  overpass import *
from road import *
import pathlib as pl


COLS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']
BBOX = (45.516012863655845,-73.61165474010419,45.54058887207495,-73.56153948806578)
HIGHWAY_LIST = ['motorway','motorway_link','trunk','trunk_link',
                'primary','primary_link','secondary','secondary_link',

                'tertiary','tertiary_link','residential']
CYCLEWAY_COL = ['cycleway', 'cycleway:both', 'cycleway:left','cycleway:right']
CYCLEWAY_LIST = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                "share_busway", "opposite_share_busway", "shared_lane", "lane"]




wd = 'tmp/'

SKIP=False

@unittest.skipIf(SKIP,'want to skip')
class SimpleTests(unittest.TestCase):
    def test_process_list_in_col(self):
        res = process_list_in_col([2,3],float,np.nanmean)
        self.assertEqual(res, 2.5)
        res = process_list_in_col([2,np.nan],float,np.nanmean)
        self.assertEqual(res, 2.0)
        res = process_list_in_col([1,2,3],float,np.sum)
        self.assertEqual(res, 6.0)
        res = process_list_in_col(5,float,np.nanmean)
        self.assertEqual(res, 5)
        res = process_list_in_col(5,str,np.nanmean)
        self.assertEqual(res, '5')
    
    def test_remove_list_in_col(self):
        res  = remove_list_in_col([1,2,3,4,5], 'first')
        self.assertEqual(res, 1)
        res  = remove_list_in_col([1,2,3,4,5], 'last')
        self.assertEqual(res, 5)
        res  = remove_list_in_col(4, 'first')
        self.assertEqual(res, 4)
        
    def test_get_epsg(self):
        res = get_epsg(45.5,-73.5)
        self.assertTrue(res, 32618)
        res = get_epsg(48.8,2.34)
        self.assertTrue(res, 32631)
  

@unittest.skipIf(SKIP,'want to skip')
class TestRead(unittest.TestCase):
    def test_get_links_and_nodes(self):
        links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
        nodes = nodes.set_crs(links.crs)
        for tag in COLS:
            self.assertTrue(tag in links.columns)
        self.assertTrue(links.crs ==  4326)
        self.assertTrue(len(links) > 0)
        self.assertEqual(links.index[0], 'road_link_0')
        self.assertEqual(nodes.index[0], 'road_node_0')

    def test_get_links_and_nodes_with_cycleway(self):
        links, nodes = get_links_and_nodes(os.path.join(wd, 'way_cycle.geojson'), split_direction=False)
        nodes = nodes.set_crs(links.crs)
        for tag in COLS + CYCLEWAY_COL:
            self.assertTrue(tag in links.columns)
        self.assertTrue(links.crs ==  4326)
        self.assertTrue(len(links) > 0)
        self.assertEqual(links.index[0], 'road_link_0')
        self.assertEqual(nodes.index[0], 'road_node_0')

@unittest.skipIf(SKIP,'want to skip')
class TestCleaning(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
        nodes = nodes.set_crs(links.crs)
        self.links = links
        self.nodes = nodes

    def test_clean_oneway(self):
        links = clean_oneway(self.links)
        self.assertSetEqual(set(links['oneway'].unique()),set([True,False]))

    def test_clean_maxspeed(self):
        links = clean_maxspeed(self.links)
        self.assertTrue(all([type(val) == np.float64 for val in links['maxspeed'].unique()]))

    def test_drop_duplicated_links(self):
        test_df = pd.DataFrame([{'a':'node_1','b':'node_2','speed':100},
                                {'a':'node_1','b':'node_2','speed':130},
                                {'a':'node_1','b':'node_2','speed':10},
                                {'a':'node_3','b':'node_4','speed':10}])
        res_df = pd.DataFrame([{'a':'node_1','b':'node_2','speed':130},
                                {'a':'node_3','b':'node_4','speed':10}])
        test_df = drop_duplicated_links(test_df, sort_column='speed')
        pd.testing.assert_frame_equal(test_df.reset_index(drop=True), res_df)



@unittest.skipIf(SKIP,'want to skip')
class TestSimplify(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
        links = links.drop(columns='tags')
        nodes = nodes.set_crs(links.crs)
        links = clean_oneway(links)
        links = clean_maxspeed(links)
        links = drop_duplicated_links(links, sort_column='maxspeed')
        self.links = links
        self.nodes = nodes
    
    def test_simplify(self):
        length = len(self.links)
        links = simplify(self.links)
        # should contain list as we merge.
        self.assertTrue(any([type(val)==list for val in links['maxspeed'].values]))
        # should have less links
        self.assertGreater(length, len(links))

    def test_split_oneway(self):
        expected_length = len(self.links) + len(self.links[self.links['oneway'] == False])
        links = split_oneway(self.links)
        # should add the correct number of links.
        self.assertEqual(len(links), expected_length)


    def test_main_strongly_connected_component(self):
        links = simplify(self.links)
        links = split_oneway(links)
        length = len(links)
        links = main_strongly_connected_component(links,None,False)
        # should remove links
        self.assertGreater(length,len(links))

        #should remove all links in this case.
        test = main_strongly_connected_component(links.iloc[0:2],None,False)
        self.assertTrue(len(test)==0)


@unittest.skipIf(SKIP,'want to skip')
class TestListCleaning(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        links, nodes = get_links_and_nodes(os.path.join(wd, 'way.geojson'), split_direction=False)
        links = links.drop(columns='tags')
        nodes = nodes.set_crs(links.crs)
        links = clean_oneway(links)
        links = clean_maxspeed(links)
        links = drop_duplicated_links(links, sort_column='maxspeed')
        links = simplify(links)
        links = split_oneway(links)
        links = main_strongly_connected_component(links,None,False)
        self.links = links
        self.nodes = nodes
    
    def test_fill_na_col(self):
        links = self.links
        links['maxspeed'] = links['maxspeed'].apply(lambda x: process_list_in_col(x,float,np.nanmean))
        links = fill_na_col(links,'highway','maxspeed',np.mean)
        self.assertTrue(all([np.isfinite(val) for val in links['maxspeed'].unique()]))






if __name__ == '__main__':
    if not os.path.exists('tmp'):
        os.makedirs('tmp')
    unittest.main()