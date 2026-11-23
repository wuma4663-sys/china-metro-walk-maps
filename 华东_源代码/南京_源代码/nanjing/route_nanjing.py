from common import *
from route import construct,connect_stations,walk_distances,interval_costs


def load_routes():
    with (folder/'routes.pkl').open('rb') as f:
        return pickle.load(f)


def adjust_station_approaches(stations):
    # Connect mapped entrances to the identified public approach on their side
    # of the road. Blind longer-distance connections remain disabled.
    for name,radius,way_ids in (
        ('板桥南',81,{165488004}),
        ('螺塘路',83,{388621185}),
        ('东山香樟园',100,{1268939633,157281041}),
        ('南京西站',74,{62358651,1497571757}),
        ('古平岗',85,{740119861}),
        ('十月广场',144,{1304191046,934630162}),
        ('东麒路',162,{917396438,1280112860}),
        ('石门坎',145,{134103801}),
    ):
        stations[name]['snap_radius']=radius
        stations[name]['snap_way_ids']=way_ids
    stations['南京西站']['station_buildings']={'南京西站'}
    # These public bus stops are the documented station approaches. Charging
    # extra walking distance keeps the missing approaches from costing zero.
    for name,id,lon,lat,radius,way_ids in (
        ('金马路',-900010,118.9035669,32.07474067,55,set()),
        ('太白',-900011,118.51025806,31.52647058,390,{346884559}),
    ):
        station = stations[name]
        bus_stop = projection.transform(lon,lat)
        exit_distance = min(hypot(bus_stop[0]-x,bus_stop[1]-y) for _,(x,y),_,_ in station['exits'])
        station['exits'].append((id,bus_stop,'公交站接驳点','公共通道估算'))
        station['access_costs']={id:round(exit_distance*1.35+20)}
        station['snap_radii']={id:radius}
        station['snap_way_ids']=way_ids


if __name__ == '__main__':
    stamp,districts,nodes,ways,polygons,relations,municipal,basemap = read_model()
    assert DISTRICTS <= districts.keys(), DISTRICTS-districts.keys()
    city = city_shape(districts,municipal)
    scope = study_area(city)
    stations=select_stations(nodes,ways,relations,scope)
    adjust_station_approaches(stations)
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
