from common import *
from route import construct,connect_stations,walk_distances,interval_costs


def load_routes():
    with (folder/'routes.pkl').open('rb') as f:
        return pickle.load(f)


def adjust_station_approaches(stations, network_ways):
    # These station approaches end on identified public roads on the same
    # side of the station. The connector length is charged in the routing.
    for name,radius,ways in (
        ('姑娘桥',180,{157356827,843545583,1447874584}),
        ('南峰',157,{1571564445,1571564446,587067964}),
        ('南湖',108,{1374970385,1374970387}),
        ('海宁高铁西站',76,{596708942,1382275778,958350660,1382275738}),
    ):
        stations[name]['snap_radius']=radius
        stations[name]['snap_way_ids']=ways
    stations['火车东站']['station_buildings']={'杭州东'}
    stations['火车西站']['snap_elevated_ways']={1084383956:16}
    ways_by_id={i:(refs,coords) for i,_,refs,coords in network_ways}
    # Use outdoor road vertices for verified public hub approaches and
    # charge for missing indoor/plaza legs.
    for name,exit_name,road,reference,extra in (
        ('火车南站','东广场公共通道',1080185979,None,24),
        ('火车西站','云谷东侧公共换乘通道',1569357815,'A',35),
        ('绍兴北站','南广场至大越路公共通道',1241378424,'C',40),
    ):
        station=stations[name]
        origin=next((xy for _,xy,ref,_ in station['exits'] if ref==reference),station['xy'])
        refs,coords=ways_by_id[road]
        distance,identifier,position=min(
            (hypot(x-origin[0],y-origin[1]),i,(x,y)) for i,(x,y) in zip(refs,coords)
        )
        station['exits'].append((identifier,position,exit_name,'公共通道估算'))
        station['access_costs']={identifier:round(distance*1.30+extra)}


if __name__ == '__main__':
    stamp,districts,nodes,ways,polygons,relations,municipal,basemap = read_model()
    assert DISTRICTS <= districts.keys(), DISTRICTS-districts.keys()
    city = city_shape(districts,municipal)
    scope = study_area(city)
    stations=select_stations(nodes,ways,relations,scope)
    adjust_station_approaches(stations,ways)
    edges,junctions,cut_geo,cut_kind=construct(scope,nodes,ways)
    names={i:t['name'] for i,t,_,_ in ways if t.get('highway') and t.get('name')}
    print('Walking graph',len(edges),'edges',len(junctions),'nodes',flush=True)
    seeds,snaps,_=connect_stations(scope,stations,nodes,edges,junctions,cut_geo,cut_kind,polygons,road_names=names)
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
    print('Outside stations with no routable entrance:',[n for n,s in stations.items() if not s['matched'] and not city.covers(Point(s['xy']))],flush=True)
    print('Stations with fewer than 35 attributed segments:',sparse,flush=True)
    print('Border stations:',[(n,round(city.distance(Point(s['xy']))),len(s['matched'])) for n,s in stations.items() if city.distance(Point(s['xy']))>1],flush=True)
    with (folder/'routes.pkl').open('wb') as f:
        pickle.dump((city,stations,edges,cut_geo,cut_kind,snaps,distances,seeds,contributions),f,protocol=5)
