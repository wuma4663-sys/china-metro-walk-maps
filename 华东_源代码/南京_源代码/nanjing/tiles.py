from math import floor

from common import *
from coverage import approx_area
from route import STRtree
from route_nanjing import load_routes

TILE=8192


if __name__=='__main__':
    _,_,_,_,areas,_,_,_=read_model()
    city,stations,edges,cut_geo,cut_kind,snaps,distances,_,_=load_routes()
    scope = study_area(city)
    active=[i for i,e in enumerate(edges) if e[0] in distances or e[1] in distances or i in snaps]
    lines=[LineString([edges[i][2],edges[i][3]]) for i in active]
    route_index=STRtree(lines)
    cuts_index=STRtree(cut_geo)
    area_index={kind:STRtree([g for _,_,g in areas[kind]]) for kind in ('water','restricted','building')}
    used=set()
    for line in lines:
        x1,y1,x2,y2=line.bounds
        used.update((x,y) for x in range(floor((x1-50)/TILE),floor((x2+50)/TILE)+1)
                    for y in range(floor((y1-50)/TILE),floor((y2+50)/TILE)+1))
    result=[]
    for x,y in sorted(used):
        tile=box(x*TILE,y*TILE,(x+1)*TILE,(y+1)*TILE)
        clip=tile.intersection(scope)
        if clip.is_empty:
            continue
        wide=tile.buffer(120)
        selected=[active[j] for j in route_index.query(wide,predicate='intersects')]
        if not selected:
            continue
        entrances={i:snaps[j] for i,j in enumerate(selected) if j in snaps}
        cut_ids=cuts_index.query(wide,predicate='intersects')
        polys={k:[areas[k][i] for i in tree.query(wide,predicate='intersects')] for k,tree in area_index.items()}
        painted,reachable=approx_area(tile,polys,[edges[i] for i in selected],
                          [cut_geo[i] for i in cut_ids],[cut_kind[i] for i in cut_ids],
                          entrances,distances,minimum_area=0,report=False)
        area=painted.intersection(clip)
        roads=reachable.intersection(clip)
        if not area.is_empty or not roads.is_empty:
            result.append((tile.bounds,area,roads))
        print(x,y,round(area.area/1e6,2),round(roads.length/1000,2),flush=True)
    print('Tiles',len(result),'area km²',round(sum(a.area for _,a,_ in result)/1e6,2),
          'route km',round(sum(r.length for _,_,r in result)/1000,2),flush=True)
    with (folder/'coverage.pkl').open('wb') as f:
        pickle.dump(result,f,protocol=5)
