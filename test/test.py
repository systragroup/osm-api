# from home
# pipenv shell to activate the env
# python tests/test_wildturkey.py 
# python -W ignore tests/test_wildturkey.py 
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
from  elevation import *
import pathlib as pl



TESTDATA_FILENAME = os.path.join(os.path.dirname(__file__), 'nodes.geojson')
URLDICT_FILENAME = os.path.join(os.path.dirname(__file__), '../url_list.json')
SKIP=False
@unittest.skipIf(SKIP,'want to skip')
class TestInit(unittest.TestCase):
    # this run only one time.
    # init and read GTFS.
    @classmethod
    def setUpClass(self):
        self.srtm='srtm3'
        self.arc=3
        self.nodes = gpd.read_file(TESTDATA_FILENAME)
        with open(URLDICT_FILENAME) as file:
            self.url_dict = json.load(file)

    def test_get_file_name(self):
        name = get_file_name(45.443,-73.6)
        self.assertEqual(name,'N45W074.hgt')
        name = get_file_name(48.93, 2.332)
        self.assertEqual(name,'N48E002.hgt')
        name = get_file_name(-36.959463, 174.856551)
        self.assertEqual(name,'S37E174.hgt')

    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))
        
    def test_fetch_data(self):
        url = self.url_dict[self.srtm]['N45W074.hgt']
        fetch_data(url)
        path = 'tmp/N45W074.hgt'
        self.assertIsFile(path)
        
    def test_read_hgt_file(self):
        path = 'tmp/N45W074.hgt'
        alt, lat, lon = read_hgt_file(path,self.arc)
        self.assertEqual(lon[0],-74)
        self.assertEqual(lon[-1],-73)
        self.assertEqual(lat[0],45)
        self.assertEqual(lat[-1],46)

        self.assertAlmostEqual(alt[0,0],186)
        self.assertAlmostEqual(alt[0,-1],364)
        self.assertAlmostEqual(alt[-1,0],94)
        self.assertAlmostEqual(alt[-1,-1],15)
        
    def test_interpolate_elevation(self):
        path = 'tmp/N45W074.hgt'
        alt, lat, lon = read_hgt_file(path,self.arc)
        lon_list = [-74,-73.5,-73]
        lat_list = [45,45.5,46]
        el = interpolate_elevation(lon_list,lat_list,alt,lon,lat)
        self.assertEqual(el, [186, 24, 15])

    def test_calc_incline(self):
        inc = calc_incline(np.array(1),np.array(2),np.array(1))
        self.assertEqual(inc,45)
        inc = calc_incline(np.array(10),np.array(9),np.array(1))
        self.assertEqual(inc,-45)
        inc = calc_incline(np.array(10),np.array(10),np.array(31))
        self.assertEqual(inc,0)
        inc = calc_incline(np.array([1, 10]),np.array([2, 10]),np.array([1,1]))
        np.testing.assert_array_equal(inc,np.array([45, 0]))
    
    def test_get_elevation_from_srtm(self):
        el_dict = get_elevation_from_srtm(self.nodes)
        self.assertEqual(len(el_dict), len(self.nodes))
        # all element are int.
        self.assertTrue(any([type(el)==int for el in el_dict.values()]))


if __name__ == '__main__':
    unittest.main()