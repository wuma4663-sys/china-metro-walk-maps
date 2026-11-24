import json
import re
import sys
from pathlib import Path

folder = Path(__file__).parent
sys.path.insert(0, str(folder.parent))
from extract_imports import *
from stations import real_stations, project_gcj, projection

DISTRICTS = {'梁溪区', '锡山区', '惠山区', '滨湖区', '新吴区', '江阴市', '宜兴市'}
GEO_EXTENT = (119.34, 30.98, 120.78, 32.12)


def sources():
    source = json.loads((folder/'amap.json').read_text(encoding='utf-8'))
    for line in source['l']:
        for station in line['st']:
            station['n'] = re.sub(r'[(（][^）)]*[）)]$', '', station['n'])
    return source


def read_model():
    with (folder/'extract.pkl').open('rb') as file:
        return pickle.load(file)


def select_stations(nodes, ways, relations, city):
    return real_stations(nodes, ways, relations, city, map_data=sources(),
                         supplemental_files=[folder/'exits.json'],
                         hub_access_enabled=False, max_entrance_distance=315)
