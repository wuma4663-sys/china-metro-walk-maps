from common import *
from route import construct,connect_stations,walk_distances,interval_costs


def load_routes():
    with (folder/'routes.pkl').open('rb') as f:
        return pickle.load(f)


def connect_known_station_approaches(stations,ways):
    # Published entrance locations place these stations on the same named
    # streets, whose OSM pedestrian approaches are partially mapped.
    for name,radius,streets in [('虎北路',94,{'虎北路','金业街'}),('古香圩',183,{'济学路'})]:
        stations[name]['snap_radius']=radius
        stations[name]['snap_roads']=streets
    hub=stations['苏州火车站']
    hub['station_buildings']={'苏州站'}
    south_square=next(LineString(xy) for oid,_,_,xy in ways if oid==620591001)
    exit_four=next(Point(xy) for _,xy,ref,_ in hub['exits'] if ref=='4')
    public_end=south_square.interpolate(south_square.project(exit_four))
    access_id=-900001
    hub['exits'].append((access_id,(public_end.x,public_end.y),'南广场公共通道','站厅接驳估算'))
    hub['access_costs']={access_id:round(exit_four.distance(public_end)*1.12+10)}


if __name__ == '__main__':
    stamp,districts,nodes,ways,polygons,relations,municipal,basemap = read_model()
    assert DISTRICTS <= districts.keys(), DISTRICTS-districts.keys()
    city = municipal[1] if municipal else shapely.union_all([g for _,g in districts.values()])
    stations=select_stations(nodes,ways,relations,city)
    connect_known_station_approaches(stations,ways)
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
