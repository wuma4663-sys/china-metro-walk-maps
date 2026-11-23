from extract_imports import *
import osmium
from stations import projection
from route import allowed, DIVIDED, FENCES


def merge_border(points,ways):
    source = work/'anting-border.osm'
    if not source.exists():
        return
    identifiers = {i for i,_,_,_ in ways}
    added = 0
    for item in osmium.FileProcessor(str(source)).with_locations('flex_mem'):
        tags = dict(item.tags)
        if item.is_node():
            if item.id in points or not item.location.valid or not (tags.get('railway') or tags.get('barrier') or tags.get('foot') or tags.get('entrance')):
                continue
            points[item.id] = (*projection.transform(item.lon,item.lat),tags)
        elif item.is_way() and item.id not in identifiers:
            h,r,w,b = (tags.get(k) for k in ('highway','railway','waterway','barrier'))
            if not (allowed(tags) or h in DIVIDED or r in {'rail','subway','light_rail','station'}
                    or b in FENCES or w in {'river','canal','stream','ditch','drain'}):
                continue
            refs = [(n.ref,n.lon,n.lat) for n in item.nodes if n.location.valid()]
            if len(refs)<2:
                continue
            xs,ys = projection.transform([r[1] for r in refs],[r[2] for r in refs])
            ways.append((item.id,tags,tuple(a for a,*_ in refs),tuple(zip(xs,ys))))
            added+=1
    print('Cross-border ways',added,flush=True)
