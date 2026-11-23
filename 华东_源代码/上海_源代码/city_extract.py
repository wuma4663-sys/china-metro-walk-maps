import hashlib
import json
import re

from extract_imports import *
import osmium
from route import allowed, DIVIDED, FENCES
from stations import project_gcj, projection, clean_name

district_names = {
    '黄浦区','徐汇区','长宁区','静安区','普陀区','虹口区','杨浦区','闵行区',
    '宝山区','嘉定区','浦东新区','金山区','松江区','青浦区','奉贤区','崇明区',
}
data = json.loads((work/'amap.json').read_text(encoding='utf-8'))
candidate_centers = [project_gcj(*map(float,s['sl'].split(','))) for w in data['l'] for s in w['st']]
route_envelope = shapely.union_all(shapely.buffer(shapely.points(candidate_centers),1900,quad_segs=12))
shapely.prepare(route_envelope)
source = work/'shanghai.osm.pbf'
assert hashlib.md5(source.read_bytes()).hexdigest() == (work/'shanghai.md5').read_text().split()[0]
reader = osmium.io.Reader(str(source))
header = reader.header()
timestamp = header.get('osmosis_replication_timestamp')
print('Verified snapshot',timestamp,header.box(),flush=True)
reader.close()
nodes, road_ways, poly, relations, coast, basemap = {}, [], defaultdict(list), [], [], defaultdict(list)
factory = osmium.geom.WKBFactory()

# A loose geographic box avoids projection of unrelated geometry while keeping the coast connected.
approx_box = (120.65,30.57,122.37,31.95)


def area_class(t, from_way):
    name = t.get('name:zh') or t.get('name')
    if not from_way and t.get('boundary')=='administrative':
        if name in district_names and t.get('admin_level') in {'5','6','7'}:
            return 'district'
        return None
    if t.get('natural')=='water' or t.get('waterway') in ('riverbank','dock') or t.get('landuse')=='reservoir':
        return 'water'
    if t.get('access') in {'private','no','military'} or t.get('landuse')=='military':
        return 'restricted'
    if 'building' in t and t.get('building') not in ('no','construction','roof'):
        return 'building'
    if t.get('leisure') in {'park','nature_reserve','golf_course','recreation_ground'} or t.get('landuse') in {'forest','grass','village_green'}:
        return 'green'
    return None


def inside_profile(wgs):
    return any(approx_box[0] <= lon <= approx_box[2] and approx_box[1] <= lat <= approx_box[3] for lon,lat in wgs)


def project_geom(geom):
    return shapely.transform(geom,projection.transform,interleaved=False)


for item in osmium.FileProcessor(str(source)).with_locations('flex_mem').with_areas():
    t = item.tags
    if item.is_node():
        h = t.get('railway')
        if not item.location.valid or not (
            h in ('subway_entrance','station','stop','halt') or
            t.get('public_transport') in ('station','stop_position') or t.get('barrier') or t.get('foot') or t.get('entrance')
        ):
            continue
        x,y = projection.transform(item.lon,item.lat)
        if shapely.intersects_xy(route_envelope,x,y):
            nodes[item.id] = (x,y,dict(t))
    elif item.is_way():
        h,r,w,b = t.get('highway'),t.get('railway'),t.get('waterway'),t.get('barrier')
        shoreline = t.get('natural')=='coastline'
        if not (shoreline or h or r or w or b):
            continue
        tags = dict(t)
        walk = allowed(tags)
        is_cut = (h in DIVIDED or r in {'rail','subway','light_rail','narrow_gauge','construction'} or
                  b in FENCES or w in {'river','canal','stream','ditch','drain'})
        draw_as = None
        if w in {'river','canal'} and not t.get('tunnel'):
            draw_as='waterline'
        elif h in DIVIDED|{'tertiary'} and t.get('tunnel') != 'yes':
            draw_as='main' if h!='tertiary' else 'minor'
        elif r in {'rail','light_rail','subway','narrow_gauge'} and t.get('tunnel')!='yes' and t.get('service') not in {'siding','spur','yard'}:
            draw_as='rail'
        elif h in {'residential','unclassified'} and t.get('tunnel')!='yes':
            draw_as='street'
        if not (walk or is_cut or draw_as or shoreline or r=='station'):
            continue
        refs = [(n.ref,n.lon,n.lat) for n in item.nodes if n.location.valid()]
        if len(refs)<2 or not inside_profile([(a,b) for _,a,b in refs]):
            continue
        xs,ys = projection.transform([row[1] for row in refs],[row[2] for row in refs])
        coords = tuple(zip(xs,ys))
        geom = LineString(coords)
        if shoreline:
            coast.append(geom)
        inside = (walk or is_cut or r=='station') and route_envelope.intersects(geom)
        if inside:
            road_ways.append((item.id,tags,tuple(a for a,*_ in refs),coords))
        if draw_as and (draw_as!='street' or inside) and geom.length>(28 if draw_as=='street' else 12):
            basemap[draw_as].append(geom)
    elif item.is_relation():
        if t.get('public_transport')=='stop_area':
            relations.append((item.id,dict(t),[(m.type,m.ref,m.role) for m in item.members]))
    elif item.is_area():
        cls = area_class(t,item.from_way())
        if cls is None:
            continue
        try:
            if cls in ('building','restricted') and not any(
                n.location.valid() and shapely.intersects_xy(route_envelope,*projection.transform(n.lon,n.lat))
                for ring in item.outer_rings() for n in ring
            ):
                continue
            geom = project_geom(shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(item))))
        except (ValueError,RuntimeError,osmium.InvalidLocationError,shapely.GEOSException):
            if cls=='district':
                raise
            continue
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        if cls in ('green','water') and geom.area<500 and not route_envelope.intersects(geom):
            continue
        poly[cls].append((item.orig_id(),dict(t),geom))
districts = {(t.get('name:zh') or t.get('name')):(i,g) for i,t,g in poly.pop('district')}
if missing := district_names-districts.keys():
    from city_boundary_fix import recover_boundaries
    districts.update(recover_boundaries(source,missing))
assert districts.keys()==district_names,district_names-districts.keys()
for name,(identifier,g) in districts.items():
    print(name,identifier,round(g.area/1e6,2),[round(a) for a in g.bounds],flush=True)
print('Retained',len(nodes),'nodes',len(road_ways),'ways',len(relations),'stop areas',
      {k:len(v) for k,v in poly.items()},len(coast),'coastline pieces',flush=True)
with (work/'city-extract.pkl').open('wb') as f:
    pickle.dump((timestamp,districts,nodes,road_ways,poly,relations,coast,basemap),f,protocol=5)
