from common import *
from route_suzhou import load_routes
from route import STRtree

_,districts,points,ways,polys,relations,_,_ = read_model()
city,stations,edges,cut_geo,cut_kind,exit_edges,distances,seeds,contributions = load_routes()
edge_geos = [LineString((e[2],e[3])) for e in edges]
t=STRtree(edge_geos)
cut_t=STRtree(cut_geo)
blocks = [(k,i,tag.get('name',''),g) for k in ('building','water','restricted') for i,tag,g in polys[k]]
b=STRtree([g for *_,g in blocks])
wi={i:t for i,t,r,geo in ways}
for name,s in stations.items():
    if s['matched']:
        continue
    print('STATION',name,'center',list(map(round,s['xy'])),flush=True)
    for ident,xy,ref,src in s['exits'] or [(0,s['xy'],'','Station center')]:
        print('exit',ident,tuple(round(a,1) for a in xy),ref,src)
        p=Point(xy)
        close = sorted((edge_geos[k].distance(p),k) for k in t.query(p,predicate='dwithin',distance=200) if edges[k][7])
        done=set()
        for d,k in close:
            if edges[k][-1] in done:
                continue
            done.add(edges[k][-1])
            pp=edge_geos[k].interpolate(edge_geos[k].project(p))
            line=LineString([p,pp])
            bis=[(x[0],x[2],round(line.intersection(x[-1]).length)) for j in b.query(line,predicate='intersects')
                if (x:=blocks[j])[-1].intersection(line).length>2]
            cis=[(cut_kind[j],round(cut_geo[j].distance(p))) for j in cut_t.query(line,predicate='crosses') if line.intersection(cut_geo[j]).distance(pp)>2]
            tags=wi.get(edges[k][-1],{})
            print('  road',round(d,1),edges[k][-1],edges[k][8],tags.get('name'),tuple(round(x,1) for x in pp.coords[0]),bis,cis)
            if len(done)>=5:
                break
    station_center=Point(s['xy'])
    road_features=[(i,t,ids,xy) for i,t,ids,xy in ways if t.get('highway') in {'footway','pedestrian','corridor','steps','path'}
                   and (t.get('indoor') or t.get('level') or t.get('covered') or t.get('tunnel'))]
    candidates=sorted((LineString(xy).distance(station_center),i,t,ids,xy) for i,t,ids,xy in road_features
                      if any(hypot(x-station_center.x,y-station_center.y)<170 for x,y in xy))
    for d,i,t,ids,xy in candidates[:10]:
        print('  indoor',round(d),i,t,[(n,[round(q,1) for q in p]) for n,p in zip(ids,xy)])
