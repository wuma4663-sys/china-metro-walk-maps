import json
from extract_imports import *
from city_stations import get_inputs
from route import construct, connect_stations, walk_distances, interval_costs
from stations import real_stations
from city_border_walk import merge_border

def load_model():
    with (work/'city-routes.pkl').open('rb') as f:
        return pickle.load(f)

if __name__=='__main__':
    stamp,districts,points,ways,areas,relations,coast,basemap = get_inputs()
    merge_border(points,ways)
    city = shapely.union_all([g for _,g in districts.values()])
    stations = real_stations(points,ways,relations,city,city=True)
    edges,junctions,cut_geo,cut_kind = construct(city,points,ways)
    print('Walking graph',len(edges),'edges and',len(junctions),'nodes',flush=True)
    road_names = {i:t['name'] for i,t,_,_ in ways if t.get('highway') and t.get('name')}
    seeds,exit_edges,snapped = connect_stations(city,stations,points,edges,junctions,cut_geo,cut_kind,areas,road_names=road_names)
    distances = walk_distances(edges,junctions,seeds)
    contributions = Counter()
    for ei,edge in enumerate(edges):
        if edge[0] not in distances and edge[1] not in distances and ei not in exit_edges:
            continue
        for s,e,origin,cost,sign,name in interval_costs(edge,distances,exit_edges.get(ei,())):
            if e>s:
                contributions[name]+=1
    print('Sources',len(seeds),'reached nodes',len(distances),'contributing stations',len(contributions),flush=True)
    missed = [name for name,s in stations.items() if not s['matched'] and city.distance(Point(s['xy']))<1020]
    sparse = [(name,len(s['matched']),contributions[name]) for name,s in stations.items()
              if len(s['matched']) and contributions[name]<45]
    print('No routable entry',missed,flush=True)
    print('Sparse attributed segments',sparse,flush=True)
    (work/'city-unmatched.json').write_text(json.dumps(missed,ensure_ascii=False),encoding='utf-8')
    with (work/'city-routes.pkl').open('wb') as f:
        pickle.dump((city,stations,edges,cut_geo,cut_kind,exit_edges,distances,seeds,contributions),f,protocol=5)
