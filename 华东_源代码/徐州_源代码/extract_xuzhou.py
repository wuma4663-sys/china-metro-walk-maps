import argparse

import osmium
import shapely
from shapely.geometry import LineString

from extract_imports import defaultdict, pickle
from network import CITY_EXTENT, COUNTIES, LINE_STATIONS, ROOT, inside, station_coordinates, projection
from route import DIVIDED, FENCES, allowed


def administrative(tags):
    if tags.get('boundary') not in {'administrative', 'political'}:
        return None
    code = tags.get('ref:admin:CN') or tags.get('division_code')
    name = tags.get('name:zh') or tags.get('name')
    if tags.get('admin_level') == '5' and name == '徐州市':
        return name
    if tags.get('admin_level') == '6':
        return COUNTIES.get(code, name if name in COUNTIES.values() else None)
    return None


def area_kind(tags):
    if tags.get('natural') == 'water' or tags.get('waterway') in {'riverbank', 'dock'} or tags.get('landuse') == 'reservoir':
        return 'water'
    if tags.get('access') in {'private', 'no', 'military'} or tags.get('landuse') == 'military':
        return 'restricted'
    if tags.get('building', 'no') not in {'no', 'construction', 'roof'}:
        return 'building'
    if tags.get('leisure') in {'park', 'nature_reserve', 'golf_course', 'recreation_ground'} or tags.get('landuse') in {'forest', 'grass', 'village_green'}:
        return 'green'
    return None


def road_layer(tags, highway, railway, waterway):
    if tags.get('tunnel') not in {None, 'no', ''}:
        return None
    if waterway in {'river', 'canal'}:
        return 'waterline'
    if highway in DIVIDED:
        return 'main'
    if highway == 'tertiary':
        return 'minor'
    if railway in {'rail', 'light_rail', 'subway'} and tags.get('service') not in {'siding', 'spur', 'yard'}:
        return 'rail'
    if highway in {'residential', 'unclassified'}:
        return 'street'
    return None


def extract(source):
    candidates, routes = station_coordinates(source)
    centers = {key: projection.transform(*location) for key, location in candidates.items()}
    envelope = shapely.union_all(shapely.buffer(shapely.points(list(centers.values())), 1950, quad_segs=12))
    shapely.prepare(envelope)
    public_stations = {'l': [
        {'ln': f'{line}号线', 'st': [{'n': name, 'xy': centers[line, name], 'poiid': f'{line}-{i:02d}'} for i, name in enumerate(names, 1)]}
        for line, names in LINE_STATIONS.items()
    ]}
    reader = osmium.io.Reader(str(source))
    stamp = reader.header().get('osmosis_replication_timestamp')
    reader.close()
    print(f'OSM snapshot {stamp} · {len(centers)} line-specific station positions', flush=True)

    points, ways, relations, boundaries = {}, [], [], {}
    polygons, basemap = defaultdict(list), defaultdict(list)
    factory = osmium.geom.WKBFactory()
    for item in osmium.FileProcessor(str(source)).with_locations('flex_mem').with_areas():
        tags = item.tags
        if item.is_node():
            if not item.location.valid() or not (
                tags.get('railway') in {'station', 'stop', 'subway_entrance', 'halt'} or
                tags.get('public_transport') in {'station', 'stop_position'} or tags.get('barrier') or tags.get('foot') or tags.get('entrance')
            ) or not inside(item.lon, item.lat):
                continue
            xy = projection.transform(item.lon, item.lat)
            if shapely.intersects_xy(envelope, *xy):
                points[item.id] = (*xy, dict(tags))
        elif item.is_way():
            h, r, w, b = (tags.get(key) for key in ('highway', 'railway', 'waterway', 'barrier'))
            if not (h or r or w or b):
                continue
            mapped_tags = dict(tags)
            walk = allowed(mapped_tags)
            cut = h in DIVIDED or r in {'rail', 'subway', 'light_rail', 'narrow_gauge', 'construction'} or b in FENCES or w in {'river', 'canal', 'stream', 'ditch', 'drain'}
            layer = road_layer(tags, h, r, w)
            if not (walk or cut or layer or r == 'station'):
                continue
            refs = [(node.ref, node.lon, node.lat) for node in item.nodes if node.location.valid()]
            if len(refs) < 2:
                continue
            in_network = any(inside(lon, lat) for _, lon, lat in refs)
            if not in_network and (not layer or layer == 'street' or not any(inside(lon, lat, CITY_EXTENT) for _, lon, lat in refs)):
                continue
            ids, lons, lats = zip(*refs)
            xy = tuple(zip(*projection.transform(lons, lats)))
            geom = LineString(xy)
            within = in_network and envelope.intersects(geom)
            if within and (walk or cut or r == 'station'):
                ways.append((item.id, mapped_tags, ids, xy))
            if layer and (within or layer != 'street') and geom.length > (24 if layer == 'street' else 16):
                basemap[layer].append(geom)
        elif item.is_relation():
            if tags.get('public_transport') == 'stop_area':
                relations.append((item.id, dict(tags), [(m.type, m.ref, m.role) for m in item.members]))
        elif item.is_area():
            admin = None if item.from_way() else administrative(tags)
            kind = None if admin else area_kind(tags)
            if not (admin or kind):
                continue
            rings = list(item.outer_rings())
            if kind:
                extent = NETWORK_EXTENT_AREA if kind in {'building', 'restricted', 'green'} else CITY_EXTENT
                if not any(node.location.valid() and inside(node.lon, node.lat, extent) for ring in rings for node in ring):
                    continue
            try:
                raw = shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(item)))
                geom = shapely.transform(raw, projection.transform, interleaved=False)
            except (ValueError, RuntimeError, osmium.InvalidLocationError, shapely.GEOSException):
                if admin:
                    raise
                continue
            if not geom.is_valid:
                geom = shapely.make_valid(geom)
            if admin:
                if admin not in boundaries or geom.area > boundaries[admin][1].area:
                    if any(inside(node.lon, node.lat, CITY_EXTENT) for ring in rings for node in ring if node.location.valid()):
                        boundaries[admin] = (item.orig_id(), geom)
            elif envelope.intersects(geom) or (kind == 'water' and geom.area > 7000) or (kind == 'green' and geom.area > 42000):
                polygons[kind].append((item.orig_id(), dict(tags), geom))

    missing = set(COUNTIES.values()) - boundaries.keys()
    if missing:
        raise ValueError(f'Missing county boundaries: {missing}')
    city = boundaries.pop('徐州市', None)
    if city is None:
        city = (None, shapely.union_all([entry[1] for entry in boundaries.values()]))
    print('County areas', [(name, oid, round(geom.area / 1e6)) for name, (oid, geom) in sorted(boundaries.items())], flush=True)
    print('Municipality', city[0], round(city[1].area / 1e6), 'km²', flush=True)
    print('Retained', len(points), len(ways), {key: len(value) for key, value in polygons.items()}, flush=True)
    with (ROOT / 'extract-xuzhou.pkl').open('wb') as out:
        pickle.dump((stamp, boundaries, points, ways, polygons, relations, city, basemap, public_stations, centers), out, protocol=5)


NETWORK_EXTENT_AREA = (116.99, 34.08, 117.40, 34.39)

if __name__ == '__main__':
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Extract Xuzhou from a Geofabrik Jiangsu PBF.')
    parser.add_argument('snapshot', type=Path)
    extract(parser.parse_args().snapshot)
