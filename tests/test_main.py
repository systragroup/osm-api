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
from main import *


COLS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']
BBOX = (45.516012863655845,-73.61165474010419,45.54058887207495,-73.56153948806578)
HIGHWAY_LIST = ['motorway','motorway_link','trunk','trunk_link',
                'primary','primary_link','secondary','secondary_link',

                'tertiary','tertiary_link','residential']
CYCLEWAY_COL = ['cycleway', 'cycleway:both', 'cycleway:left','cycleway:right']
CYCLEWAY_LIST = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                "share_busway", "opposite_share_busway", "shared_lane"]

POLY = [[-74.0204, 40.6961], [-74.0110, 40.7506], [-73.9673, 40.7444], [-73.9671, 40.7296], [-73.9745, 40.70946], [-73.9941, 40.7067], [-74.0204, 40.6961]]


wd = 'tmp/'

SKIP=False


@unittest.skipIf(SKIP,'want to skip')
class TestMainCycleway(unittest.TestCase):
    def test_osm_simplify_1(self):
        add_elevation=True
        split_direction=False
        links, nodes = osm_importer(BBOX,HIGHWAY_LIST+['cycleway'],CYCLEWAY_LIST,False,wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'cycleway', 'a', 'b', 'geometry', 'cycleway_reverse', 'length', 'time', 'incline']
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry','elevation']))
        self.assertTrue(True in links['oneway'].unique())

    def test_osm_simplify_2(self):
        add_elevation=False
        split_direction=True
        links, nodes = osm_importer(BBOX,HIGHWAY_LIST+['cycleway'],CYCLEWAY_LIST,False,wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'cycleway', 'a', 'b', 'geometry', 'cycleway_reverse', 'length', 'time']
        
        self.assertSetEqual( set(links['cycleway'].unique()), set(['no','yes','shared']))
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry']))
        self.assertTrue(False not in links['oneway'].unique())

    def test_osm_simplify_3(self):
        add_elevation=True
        split_direction=False
        links, nodes = osm_importer(BBOX,HIGHWAY_LIST+['cycleway'],CYCLEWAY_LIST,False,wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'cycleway', 'a', 'b', 'geometry', 'cycleway_reverse', 'length', 'time', 'incline']
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry','elevation']))

        self.assertTrue(True in links['oneway'].unique())

    def test_osm_simplify_4(self):
        add_elevation=True
        split_direction=False
        extended_cycleway=True
        links, nodes = osm_importer(BBOX,HIGHWAY_LIST+['cycleway'],CYCLEWAY_LIST,extended_cycleway,wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'cycleway', 'a', 'b', 'geometry', 'cycleway_reverse', 'length', 'time', 'incline']
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry','elevation']))

        self.assertTrue(True in links['oneway'].unique())

@unittest.skipIf(SKIP,'want to skip')
class TestMainHighway(unittest.TestCase):


    def test_osm_simplify_1(self):
        add_elevation=True
        split_direction=False
        links, nodes= osm_importer(BBOX,HIGHWAY_LIST, None, False, wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'a', 'b', 'geometry', 'length', 'time', 'incline']
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry','elevation']))
        self.assertTrue(True in links['oneway'].unique())

    def test_osm_simplify_2(self):
        add_elevation=False
        split_direction=True
        links, nodes = osm_importer(BBOX,HIGHWAY_LIST, None, False, wd)
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'a', 'b', 'geometry', 'length', 'time']
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry']))
        self.assertTrue(False not  in links['oneway'].unique())

    def test_osm_simplify_3(self):
        add_elevation=True
        split_direction=False
        bbox = get_bbox(POLY)
        links, nodes = osm_importer(bbox,HIGHWAY_LIST, None, False, wd)
        links = gpd.sjoin(links, gpd.GeoDataFrame(geometry=[Polygon(POLY)],crs=4326), how='inner', predicate='intersects').drop(columns='index_right')
        links, nodes = osm_simplify(links, nodes, HIGHWAY_LIST, add_elevation, split_direction)
        expected_res = ['highway', 'speed', 'lanes', 'name', 'oneway', 'surface', 'a', 'b', 'geometry', 'length', 'time', 'incline']
        print(links.columns)
        self.assertSetEqual( set(links.columns),set(expected_res))
        self.assertSetEqual( set(nodes.columns),set(['geometry','elevation']))
        self.assertTrue(True in links['oneway'].unique())










if __name__ == '__main__':
    if not os.path.exists('tmp'):
        os.makedirs('tmp')
    unittest.main()