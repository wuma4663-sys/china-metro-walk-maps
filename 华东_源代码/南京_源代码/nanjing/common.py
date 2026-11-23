import json
import sys
from pathlib import Path

folder = Path(__file__).parent
sys.path.insert(0, str(folder.parent))
from extract_imports import *
from stations import real_stations, project_gcj, projection

DISTRICTS = {
    '玄武区','秦淮区','建邺区','鼓楼区','浦口区','栖霞区',
    '雨花台区','江宁区','六合区','溧水区','高淳区',
}
GEO_EXTENT = (118.26,31.15,119.36,32.65)
EXTERNAL_LINES = {'S2': ('马鞍山市',8), 'S6': ('镇江市 · 句容市',8)}
DISPLAY_NAMES = {'板桥':'板桥·梅山钢铁','刘村':'刘村·弘阳家居博览中心'}


def sources():
    return json.loads((folder/'amap.json').read_text(encoding='utf-8'))


def external_stops():
    result = {}
    for line in sources()['l']:
        key = next((key for key in EXTERNAL_LINES if line['ln'].startswith(key+'号线')), None)
        if key:
            label, start = EXTERNAL_LINES[key]
            result[key] = (label, {st['n']:project_gcj(*map(float,st['sl'].split(',')))
                                   for st in line['st'][start:]})
    return result


def external_areas(city):
    return {key:shapely.union_all(shapely.buffer(shapely.points(list(stops.values())),1650,quad_segs=20)).difference(city)
            for key,(_,stops) in external_stops().items()}


def study_area(city):
    return shapely.union_all([city,*external_areas(city).values()])


def city_shape(districts, municipal):
    return municipal[1] if municipal else shapely.union_all([g for _,g in districts.values()])


def read_model():
    with (folder/'extract.pkl').open('rb') as file:
        result = pickle.load(file)
    other = folder/'extract-anhui.pkl'
    with other.open('rb') as file:
        _,_,external_nodes,external_ways,external_poly,external_rel,_,external_base = pickle.load(file)
    stamp,districts,nodes,ways,poly,relations,municipal,base = result
    nodes.update(external_nodes)
    for current, additional in ((ways,external_ways),(relations,external_rel)):
        ids = {entry[0] for entry in current}
        current.extend(entry for entry in additional if entry[0] not in ids)
    for kind, additions in external_poly.items():
        ids = {entry[0] for entry in poly[kind]}
        poly[kind].extend(entry for entry in additions if entry[0] not in ids)
    for kind, additions in external_base.items():
        base[kind].extend(additions)
    return stamp,districts,nodes,ways,poly,relations,municipal,base


def select_stations(nodes, ways, relations, city):
    return real_stations(nodes, ways, relations, city, map_data=sources(),
                         supplemental_files=[folder/'exits.json',folder/'verified-exits.json'],
                         hub_access_enabled=False,max_entrance_distance=335)
