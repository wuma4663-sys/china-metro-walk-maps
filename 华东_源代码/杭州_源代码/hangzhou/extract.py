import argparse
import hashlib

from common import *
import osmium
from route import allowed,DIVIDED,FENCES

codes = {'330102':'上城区','330105':'拱墅区','330106':'西湖区','330108':'滨江区',
         '330109':'萧山区','330110':'余杭区','330111':'富阳区','330112':'临安区',
         '330113':'临平区','330114':'钱塘区','330122':'桐庐县','330127':'淳安县','330182':'建德市'}
lon0,lat0,lon1,lat1=GEO_EXTENT


def in_area(lon,lat):
    return lon0<=lon<=lon1 and lat0<=lat<=lat1


def administrative(t):
    if t.get('boundary') not in {'administrative','political'}:
        return None
    ident = t.get('ref:admin:CN') or t.get('division_code')
    name = t.get('name:zh') or t.get('name')
    if t.get('admin_level')=='6':
        # The snapshot's repurposed Linping relation retains its old Yuhang code.
        if name=='临平区' and ident=='330110':
            return name
        if ident:
            return codes.get(ident)
        return name if name in DISTRICTS else None
    if t.get('admin_level')=='5' and name=='杭州市':
        return name
    return None


def area_kind(t,from_way):
    if not from_way and administrative(t):
        return 'district'
    if t.get('natural')=='water' or t.get('waterway') in ('riverbank','dock') or t.get('landuse')=='reservoir':
        return 'water'
    if t.get('access') in {'private','no','military'} or t.get('landuse')=='military':
        return 'restricted'
    if 'building' in t and t['building'] not in ('no','construction','roof'):
        return 'building'
    if t.get('leisure') in {'park','nature_reserve','golf_course','recreation_ground'} or t.get('landuse') in {'forest','grass','village_green'}:
        return 'green'
    return None


def road_layer(t,h,r,w):
    if w in {'river','canal'} and not t.get('tunnel'):
        return 'waterline'
    if t.get('tunnel')=='yes':
        return None
    if h in DIVIDED|{'tertiary'}:
        return 'main' if h!='tertiary' else 'minor'
    if r in {'rail','light_rail','subway'} and t.get('service') not in {'siding','spur','yard'}:
        return 'rail'
    if h in {'residential','unclassified'}:
        return 'street'


parser = argparse.ArgumentParser(description='Extract the map and walking network from a verified OSM snapshot.')
parser.add_argument('snapshot',type=Path)
args = parser.parse_args()
source = args.snapshot
checksum = folder/'zhejiang.md5'
expected = checksum.read_text(encoding='ascii').split()[0]
with source.open('rb') as handle:
    actual = hashlib.file_digest(handle,'md5').hexdigest()
if actual != expected:
    raise SystemExit(f'快照校验失败 {source}\n预期 {expected}\n实际 {actual}')

data=sources()
centers=[project_gcj(*map(float,s['sl'].split(','))) for line in data['l'] for s in line['st']
         if in_area(*map(float,s['sl'].split(',')))]
envelope=shapely.union_all(shapely.buffer(shapely.points(centers),1950,quad_segs=10))
shapely.prepare(envelope)
reader=osmium.io.Reader(str(source))
stamp=reader.header().get('osmosis_replication_timestamp')
print('Verified snapshot',stamp,reader.header().box(),flush=True)
reader.close()
nodes,ways,poly,rel,boundaries,base={},[],defaultdict(list),[],{},defaultdict(list)
factory=osmium.geom.WKBFactory()

for item in osmium.FileProcessor(str(source)).with_locations('flex_mem').with_areas():
    t=item.tags
    if item.is_node():
        if not item.location.valid or not (
            t.get('railway') in {'station','stop','subway_entrance','halt'} or
            t.get('public_transport') in {'station','stop_position'} or t.get('barrier') or t.get('foot') or t.get('entrance')
        ) or not in_area(item.lon,item.lat):
            continue
        x,y=projection.transform(item.lon,item.lat)
        if shapely.intersects_xy(envelope,x,y):
            nodes[item.id]=(x,y,dict(t))
    elif item.is_way():
        h,r,w,b=(t.get(k) for k in ('highway','railway','waterway','barrier'))
        if not (h or r or w or b):
            continue
        tags=dict(t)
        walk=allowed(tags)
        cut=(h in DIVIDED or r in {'rail','subway','light_rail','narrow_gauge','construction'}
             or b in FENCES or w in {'river','canal','stream','ditch','drain'})
        layer=road_layer(t,h,r,w)
        if not (walk or cut or layer or r=='station'):
            continue
        refs=[(n.ref,n.lon,n.lat) for n in item.nodes if n.location.valid()]
        if len(refs)<2 or not any(in_area(a,b) for _,a,b in refs):
            continue
        xs,ys=projection.transform([a for _,a,_ in refs],[b for _,_,b in refs])
        xy=tuple(zip(xs,ys))
        g=LineString(xy)
        within=(walk or cut or r=='station') and envelope.intersects(g)
        if within:
            ways.append((item.id,tags,tuple(n for n,*_ in refs),xy))
        if layer and (within or layer!='street') and g.length>(28 if layer=='street' else 12):
            base[layer].append(g)
    elif item.is_relation():
        if t.get('public_transport')=='stop_area':
            rel.append((item.id,dict(t),[(m.type,m.ref,m.role) for m in item.members]))
    elif item.is_area():
        kind=area_kind(t,item.from_way())
        if kind is None:
            continue
        if kind!='district':
            rings=list(item.outer_rings())
            if not any(n.location.valid() and in_area(n.lon,n.lat) for ring in rings for n in ring):
                continue
            if kind in {'building','restricted'} and not any(
                 n.location.valid() and shapely.intersects_xy(envelope,*projection.transform(n.lon,n.lat))
                 for ring in rings for n in ring
            ):
                continue
        try:
            geom=shapely.transform(shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(item))),
                                   projection.transform,interleaved=False)
        except (ValueError,RuntimeError,osmium.InvalidLocationError,shapely.GEOSException):
            if kind=='district':
                raise
            continue
        if not geom.is_valid:
            geom=shapely.make_valid(geom)
        if kind=='district':
            name=administrative(t)
            previous=boundaries.get(name)
            if not previous or geom.area>previous[1].area:
                boundaries[name]=(item.orig_id(),geom)
        elif kind not in {'water','green'} or geom.area>=450 or envelope.intersects(geom):
            poly[kind].append((item.orig_id(),dict(t),geom))

print('County polygons:',[(n,i,round(g.area/1e6,2)) for n,(i,g) in boundaries.items()],flush=True)
display={n:v for n,v in boundaries.items() if n in DISTRICTS}
missing = DISTRICTS-display.keys()
if missing:
    print('Missing boundary relations',missing,flush=True)
city=boundaries.get('杭州市')
if city:
    print('Municipal polygon',city[0],round(city[1].area/1e6,2),'km²',flush=True)
print('Retained',len(nodes),len(ways),len(rel),{k:len(v) for k,v in poly.items()},flush=True)
with (folder/'extract.pkl').open('wb') as f:
    pickle.dump((stamp,display,nodes,ways,poly,rel,city,base),f,protocol=5)
