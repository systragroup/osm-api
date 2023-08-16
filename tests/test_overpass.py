import sys
import unittest
import os
import json
sys.path.insert(0, r'../osm-api/')
from  overpass import *
import pathlib as pl


COLS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']
BBOX = (45.516012863655845,-73.61165474010419,45.54058887207495,-73.56153948806578)
HIGHWAY_LIST = ['motorway','motorway_link','trunk','trunk_link',
                'primary','primary_link','secondary','secondary_link',

                'tertiary','tertiary_link','residential']
CYCLEWAY_COL = ['cycleway', 'cycleway:both', 'cycleway:left','cycleway:right']
CYCLEWAY_LIST = ["lane", "opposite", "opposite_lane", "track", "opposite_track", 
                "share_busway", "opposite_share_busway", "shared_lane"]




wd = 'tmp/'

SKIP=False

@unittest.skipIf(SKIP,'want to skip')
class TestFetch(unittest.TestCase):
    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))
        
    def test_get_overpass_query(self):
        overpass_query = get_overpass_query(BBOX, HIGHWAY_LIST)
        self.assertTrue('way["highway"="residential"]' in overpass_query)
        self.assertTrue('way["cycleway"="lane"]' not in overpass_query)
        self.assertTrue(str(BBOX) in overpass_query)

    def test_get_overpass_query_with_cycleway(self):
        overpass_query = get_overpass_query(BBOX, HIGHWAY_LIST,CYCLEWAY_LIST)
        self.assertTrue('way["highway"="residential"]' in overpass_query)
        self.assertTrue('way["cycleway"="lane"]' in overpass_query)
        self.assertTrue(str(BBOX) in overpass_query)
        
    def test_fetch_overpass(self):
        overpass_query = get_overpass_query(BBOX, HIGHWAY_LIST)
        fetch_overpass(overpass_query,COLS,wd)
        path = 'tmp/way.geojson'
        self.assertIsFile(path)

    def test_fetch_overpass_with_cycleway(self):
        overpass_query = get_overpass_query(BBOX, HIGHWAY_LIST, CYCLEWAY_LIST)
        fetch_overpass(overpass_query, COLS + CYCLEWAY_COL, wd, 'way_cycle.geojson')
        path = 'tmp/way_cycle.geojson'
        self.assertIsFile(path)

    def test_get_bbox(self):
        poly = [ [-74.021412, 40.696947], [-73.998055, 40.7603484], [-74.021472, 40.696069] ]
        bbox = get_bbox(poly)
        self.assertEqual(bbox,(40.696069, -74.021472, 40.7603484, -73.998055))



if __name__ == '__main__':
    if not os.path.exists('tmp'):
        os.makedirs('tmp')
    unittest.main()