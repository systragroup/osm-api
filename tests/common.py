import os
import json
from pathlib import Path

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

CYCLEWAY_COLUMNS = ['cycleway:both', 'cycleway:left', 'cycleway:right']
HIGHWAY_COLUMNS = ['highway', 'maxspeed', 'lanes', 'name', 'oneway', 'surface']


def get_path():
	current_path = Path(__file__).parent
	return os.path.join(current_path, 'data')


def to_json(data, name='output.json'):
	with open(name, 'w') as json_file:
		json.dump(data, json_file, indent=4)


def read_json(name='output.json'):

	with open(name) as f:
		return json.load(f)
