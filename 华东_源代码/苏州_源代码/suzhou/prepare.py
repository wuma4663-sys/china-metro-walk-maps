from common import *

if __name__=='__main__':
    stamp,districts,nodes,ways,polys,relations,coast,basemap=read_model()
    city = shapely.union_all([g for _,g in districts.values()])
    stations = select_stations(nodes,ways,relations,city)
    output = {name:{**s,'border_distance':city.distance(Point(s['xy'])), 
                    'distance_at_least_one_exit':min([city.distance(Point(xy)) for _,xy,_,_ in s['exits']],default=float('inf'))}
              for name,s in stations.items()}
    (folder/'stations.json').write_text(json.dumps(output,ensure_ascii=False),encoding='utf-8')
    internal = {name:s for name,s in output.items() if s['border_distance']<1}
    missing = [name for name,s in internal.items() if not s['exits']]
    print('City',round(city.area/1e6,1),city.bounds,'km² and UTM bounds',flush=True)
    print('Stations',len(internal),'in city',sum(len(s['exits']) for s in internal.values()),'exits',flush=True)
    print('Stations without mapped exits',len(missing),missing,flush=True)
    print('Exit count histogram',dict(sorted(Counter(len(s['exits']) for s in internal.values()).items())),flush=True)
    print('Nearby external stations',[(name,round(s['border_distance']),len(s['exits'])) for name,s in output.items() if s['border_distance']>1],flush=True)
