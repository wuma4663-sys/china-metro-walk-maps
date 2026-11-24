from common import *
from route import construct,connect_stations,walk_distances,interval_costs


def load_routes():
    with (folder/'routes.pkl').open('rb') as f:
        return pickle.load(f)


if __name__ == '__main__':
    stamp,districts,nodes,ways,polygons,relations,municipal,basemap = read_model()
    assert DISTRICTS <= districts.keys(), DISTRICTS-districts.keys()
    city = municipal[1] if municipal else shapely.union_all([g for _,g in districts.values()])
    stations=select_stations(nodes,ways,relations,city)
    edges,junctions,cut_geo,cut_kind=construct(city,nodes,ways)
    names={i:t['name'] for i,t,_,_ in ways if t.get('highway') and t.get('name')}
    print('Walking graph',len(edges),'edges',len(junctions),'nodes',flush=True)
    seeds,snaps,_=connect_stations(city,stations,nodes,edges,junctions,cut_geo,cut_kind,polygons,road_names=names)
    distances=walk_distances(edges,junctions,seeds)
    contributions=Counter()
    for index,edge in enumerate(edges):
        if edge[0] not in distances and edge[1] not in distances and index not in snaps:
            continue
        for lo,hi,_,_,_,name in interval_costs(edge,distances,snaps.get(index,())):
            if lo<hi:
                contributions[name]+=1
    print('Connected',sum(bool(s['matched']) for s in stations.values()),'stations and',len(distances),'road nodes',flush=True)
    missing=[n for n,s in stations.items() if not s['matched'] and city.distance(Point(s['xy']))<1]
    sparse=[(n,len(s['matched']),contributions[n]) for n,s in stations.items() if s['matched'] and contributions[n]<35]
    print('Stations with no routable entrance:',missing,flush=True)
    print('Stations with fewer than 35 attributed segments:',sparse,flush=True)
    print('Border stations:',[(n,round(city.distance(Point(s['xy']))),len(s['matched'])) for n,s in stations.items() if city.distance(Point(s['xy']))>1],flush=True)
    with (folder/'routes.pkl').open('wb') as f:
        pickle.dump((city,stations,edges,cut_geo,cut_kind,snaps,distances,seeds,contributions),f,protocol=5)
