from extract_imports import *
import osmium
from shapely.ops import polygonize_full
from pyproj import Transformer
import xml.etree.ElementTree as ET


def recover_boundaries(source, district_names):
    file = str(source)
    boundary_relations = {}
    needed = set()
    for row in osmium.FileProcessor(file,osmium.osm.RELATION):
        t = row.tags
        name = t.get('name:zh') or t.get('name')
        if t.get('boundary')=='administrative' and t.get('admin_level')=='6' and name in district_names:
            members = [(m.role,m.ref) for m in row.members if m.type=='w' and m.role in {'outer','inner',''}]
            boundary_relations[name] = (row.id,members)
            needed.update(ref for _,ref in members)
    project = Transformer.from_crs(4326,32651,always_xy=True)
    way_geoms = {}
    for item in osmium.FileProcessor(file,osmium.osm.NODE|osmium.osm.WAY).with_locations('flex_mem').with_filter(osmium.filter.EntityFilter(osmium.osm.WAY)):
        if item.id not in needed:
            continue
        coords = [(n.lon,n.lat) for n in item.nodes if n.location.valid()]
        if len(coords)>1:
            way_geoms[item.id] = shapely.transform(LineString(coords),project.transform,interleaved=False)
    results = {}
    for name,(relation,members) in boundary_relations.items():
        local = work/f"bound-{ {'静安区':'jingan','宝山区':'baoshan'}.get(name,'') }.osm"
        if local.exists() and local.stat().st_size>100:
            tree=ET.parse(local)
            root=tree.getroot()
            ps = {int(n.attrib['id']): (float(n.attrib['lon']),float(n.attrib['lat'])) for n in root.findall('node')}
            rel = root.find(f"./relation[@id='{relation}']")
            if rel is not None:
                live = {(m.get('role',''),int(m.attrib['ref'])) for m in rel.findall('member') if m.get('type')=='way'}
                complete = {w:tuple(ps[int(n.attrib['ref'])] for n in geom.findall('nd'))
                            for geom in root.findall('way') for w in (int(geom.attrib['id']),)}
                for role,ref in members:
                    if (role,ref) in live and ref not in way_geoms and ref in complete:
                        way_geoms[ref] = shapely.transform(LineString(complete[ref]),project.transform,interleaved=False)
        missing = [ref for _,ref in members if ref not in way_geoms]
        print(name,relation,'missing ways:',missing,flush=True)
        outer = [way_geoms[ref] for role,ref in members if role!='inner' and ref in way_geoms]
        inner = [way_geoms[ref] for role,ref in members if role=='inner' and ref in way_geoms]
        def assembled(lines):
            full = shapely.union_all(lines)
            polys,cuts,dangles,invalid = polygonize_full(shapely.get_parts(full))
            print('assembly lengths',*[round(g.length,1) for g in (cuts,dangles,invalid)],flush=True)
            return shapely.union_all(shapely.get_parts(polys))
        footprint = assembled(outer)
        if inner:
            footprint = footprint.difference(assembled(inner))
        assert footprint.area>1e6,(name,footprint)
        results[name] = (relation,footprint)
    return results


if __name__=='__main__':
    recovered = recover_boundaries(work/'shanghai.osm.pbf',{'静安区','宝山区'})
    for name,(_,g) in recovered.items():
        print(name,g.geom_type,round(g.area/1e6,2),g.bounds)
