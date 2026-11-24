import json
import math
import re
from collections import defaultdict

from extract_imports import Point, Polygon, LineString, work, hypot
from pyproj import Transformer

projection = Transformer.from_crs(
    4326, '+proj=tmerc +lat_0=0 +lon_0=120 +k=1 +x_0=500000 +ellps=WGS84 +units=m',
    always_xy=True,
)


def project_gcj(lon, lat):
    x, y = lon - 105, lat - 35
    lat_delta = (
        -100 + 2*x + 3*y + .2*y*y + .1*x*y + .2*math.sqrt(abs(x))
        + (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi))*2/3
        + (20*math.sin(y*math.pi) + 40*math.sin(y*math.pi/3))*2/3
        + (160*math.sin(y*math.pi/12) + 320*math.sin(y*math.pi/30))*2/3
    )
    lon_delta = (
        300 + x + 2*y + .1*x*x + .1*x*y + .1*math.sqrt(abs(x))
        + (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi))*2/3
        + (20*math.sin(x*math.pi) + 40*math.sin(x*math.pi/3))*2/3
        + (150*math.sin(x*math.pi/12) + 300*math.sin(x*math.pi/30))*2/3
    )
    angle = math.radians(lat)
    magic = 1 - .006693421622965943 * math.sin(angle)**2
    lat_delta = lat_delta*180 / (6378245*(1-.006693421622965943)/(magic**1.5)*math.pi)
    lon_delta = lon_delta*180 / (6378245/math.sqrt(magic)*math.cos(angle)*math.pi)
    return projection.transform(lon-lon_delta, lat-lat_delta)


def clean_name(value):
    value = re.split(r'[（(]\d+号线[)）]', value)[0]
    return value.replace('・', '·').strip()


def real_stations(points, ways, relations, district, *, city=False, map_data=None, supplemental_files=None, hub_access_enabled=True, max_entrance_distance=335):
    listed = defaultdict(list)
    map_data = map_data or json.loads((work/'amap.json').read_text(encoding='utf-8'))
    for line in map_data['l']:
        if line['ln'] == '磁浮线' and not city:
            continue
        for st in line['st']:
            position = project_gcj(*map(float, st['sl'].split(',')))
            if district.distance(Point(position)) <= 1700:
                listed[clean_name(st['n'])].append((line['ln'], position, st['poiid']))
    output = {}
    way_index = {i:(tags, coords) for i,tags,_,coords in ways if tags.get('railway') == 'station'}
    source_by_id = {}
    station_areas = defaultdict(list)
    for rid,tags,members in relations:
        if tags.get('public_transport')=='stop_area':
            station_areas[clean_name(tags.get('name',''))].append(members)
    for name, entries in listed.items():
        line_names = list(dict.fromkeys(line for line,_,_ in entries))
        geo_reference = entries[0][1]
        relevant = set()
        centers = []
        for members in station_areas[name]:
            current = []
            entries_in_area = []
            for kind, ref, role in members:
                if kind == 'n' and ref in points:
                    x,y,t = points[ref]
                    if t.get('railway') == 'subway_entrance':
                        entries_in_area.append(ref)
                    elif role in ('station', 'stop', 'stop_position') or t.get('railway') in ('station','stop'):
                        current.append((0 if role=='station' or t.get('railway')=='station' else 1,(x,y)))
                if kind == 'w' and role == 'station' and ref in way_index:
                    _, coords = way_index[ref]
                    shape = Polygon(coords) if len(coords)>3 and coords[0]==coords[-1] else LineString(coords)
                    current.append((0,tuple(shape.centroid.coords)[0]))
            if not current or min(hypot(x-gx,y-gy) for _,(x,y) in current for _,(gx,gy),_ in entries)>570:
                continue
            centers.extend(current)
            relevant.update(entries_in_area)
        if centers:
            best_center = min(centers,key=lambda a:(a[0],hypot(a[1][0]-geo_reference[0],a[1][1]-geo_reference[1])))[1]
        else:
            matches = [(x,y) for x,y,t in points.values() if t.get('railway')=='station'
                       and clean_name(t.get('name',''))==name and hypot(x-geo_reference[0],y-geo_reference[1])<450]
            best_center = min(matches,key=lambda xy:hypot(xy[0]-geo_reference[0],xy[1]-geo_reference[1]),default=geo_reference)
        output[name] = {'xy':best_center, 'lines':line_names, 'poi':entries[0][2], 'exits':[]}
        source_by_id.update((ref,name) for ref in relevant)
    for identifier,(x,y,t) in points.items():
        if t.get('railway') != 'subway_entrance':
            continue
        name = source_by_id.get(identifier)
        if name is None:
            nearest = min(output,key=lambda key:hypot(x-output[key]['xy'][0],y-output[key]['xy'][1]))
            a,b = output[nearest]['xy']
            if hypot(x-a,y-b) < max_entrance_distance:
                name = nearest
        if name is not None:
            output[name]['exits'].append((identifier,(x,y),t.get('ref',''), 'OSM'))
    supplemental = []
    if supplemental_files is None:
        supplemental_files = [work/'supplement.json',work/'hub_exits.json']
        if city:
            supplemental_files.append(work/'city-exits.json')
    for extra in supplemental_files:
        if extra.exists():
            supplemental.extend(json.loads(extra.read_text(encoding='utf-8')))
    if supplemental:
        for i,item in enumerate(supplemental):
            name = item['station']
            if name not in output:
                continue
            if 'node' in item:
                xy = points[item['node']][:2]
                ident = item['node']
            elif 'xy' in item:
                xy = tuple(item['xy'])
                ident = -1000-i
            else:
                map_transform = project_gcj if item.get('crs')=='gcj02' else projection.transform
                xy = map_transform(item['lon'],item['lat'])
                ident = -1000-i
            center = output[name]['xy']
            if hypot(xy[0]-center[0],xy[1]-center[1]) <= 680 and all(
                hypot(xy[0]-x,xy[1]-y)>item.get('minimum_separation',10) for _,(x,y),_,_ in output[name]['exits']
            ):
                output[name]['exits'].append((ident,xy,item['exit'],item['source']))
    if not hub_access_enabled:
        return output
    hub_access = {'虹桥火车站':(4460193672,5019791794), '虹桥2号航站楼':(605019372,5313309153)}
    for name, identifiers in hub_access.items():
        if name not in output:
            continue
        for identifier in identifiers:
            if identifier in points:
                output[name]['exits'].append((identifier,points[identifier][:2],'公共站厅接点','OSM 站内通道'))
    if city and '浦东1号2号航站楼' in output:
        entrances = {3395151066,8050097480}
        coords = {identifier:pt for i,_,refs,geometry in ways if i in {966184833,332394479}
                  for identifier,pt in zip(refs,geometry) if identifier in entrances}
        for identifier,pt in coords.items():
            output['浦东1号2号航站楼']['exits'].append((identifier,pt,'公共站厅接点','OSM 站内通道'))
    return output


if __name__ == '__main__':
    from extract_imports import read
    _, points, ways, areas, relations, _ = read()
    district = next(g for k,_,_,g in areas if k=='district')
    stations = real_stations(points,ways,relations,district)
    for name, s in stations.items():
        if district.distance(Point(s['xy'])) < 1600 or s['exits']:
            print(name, '/'.join(s['lines']), round(district.distance(Point(s['xy']))),
                  s['poi'], ' | '.join(f'{i} {tag}' for i,_,tag,_ in s['exits']))
