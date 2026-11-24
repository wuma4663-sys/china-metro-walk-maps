import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder.parent))
from extract_imports import *
from stations import real_stations, project_gcj, projection

DISTRICTS = {
    '上城区','拱墅区','西湖区','滨江区','萧山区','余杭区','临平区',
    '钱塘区','富阳区','临安区','桐庐县','淳安县','建德市',
}
GEO_EXTENT = (118.30,29.10,120.85,30.65)
CROSS_LINES = {
    'haining': ('杭海城际', '嘉兴市海宁市'),
    'shaoxing': ('绍兴1号线', '绍兴市'),
}


def sources():
    return json.loads((folder/'amap.json').read_text(encoding='utf-8'))


def external_stops(city):
    output = {key:(place,{}) for key,(_,place) in CROSS_LINES.items()}
    for line in sources()['l']:
        for key,(prefix,_) in CROSS_LINES.items():
            if not line['ln'].startswith(prefix):
                continue
            for stop in line['st']:
                position = project_gcj(*map(float,stop['sl'].split(',')))
                if not city.covers(Point(position)):
                    output[key][1][stop['n']] = position
    return output


def external_areas(city):
    return {
        key:shapely.union_all(shapely.buffer(shapely.points(list(stops.values())),1650,quad_segs=20)).difference(city)
        for key,(_,stops) in external_stops(city).items()
    }


def study_area(city):
    return shapely.union_all([city,*external_areas(city).values()])


def city_shape(districts, municipal):
    return municipal[1] if municipal else shapely.union_all([g for _,g in districts.values()])


def read_model():
    with (folder/'extract.pkl').open('rb') as file:
        return pickle.load(file)


def select_stations(nodes, ways, relations, city):
    return real_stations(nodes, ways, relations, city, map_data=sources(),
                         supplemental_files=[folder/'exits.json',folder/'verified-exits.json'],
                         hub_access_enabled=False,max_entrance_distance=360)
