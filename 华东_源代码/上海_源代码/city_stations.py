import json
from extract_imports import *
from stations import real_stations


def get_inputs():
    with (work/'city-extract.pkl').open('rb') as handle:
        return pickle.load(handle)


if __name__ == '__main__':
    stamp,districts,nodes,ways,areas,relations,coast,basemap = get_inputs()
    city = shapely.union_all([g for _,g in districts.values()])
    print('City shape:',city.geom_type,round(city.area/1e6,2),[round(x) for x in city.bounds],flush=True)
    stations = real_stations(nodes,ways,relations,city,city=True)
    stats = {name:{**s,'border_distance':city.distance(Point(s['xy']))} for name,s in stations.items()}
    (work/'city-stations.json').write_text(json.dumps(stats,ensure_ascii=False),encoding='utf-8')
    print('Candidates:',len(stats),'No entrances:',[name for name,s in stats.items() if not s['exits']],flush=True)
    print('Outside:',[(name,round(s['border_distance'])) for name,s in stats.items() if s['border_distance']>3],flush=True)
