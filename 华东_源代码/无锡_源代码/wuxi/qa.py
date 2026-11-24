from xml.etree import ElementTree
from common import *
from route_wuxi import load_routes
from route import LIMIT, interval_costs

stamp,districts,*_ = read_model()
city,original,edges,*_ = load_routes()
with (folder/'augmented.pkl').open('rb') as f:
    stations,combined,snaps,estimated,supplemental_snaps=pickle.load(f)
source = sources()
names={s['n'] for line in source['l'] for s in line['st']}
assert set(districts)==DISTRICTS
assert len(names)==89 and set(stations)==names
assert {line['ln'] for line in source['l']}=={'1号线','2号线','3号线','4号线','S1线'}
assert all(station['matched'] for station in stations.values())
assert all(city.covers(Point(station['xy'])) for station in stations.values())
assert all(d<=LIMIT for d,_ in combined.values())
assert sum(s.get('estimated',False) for s in stations.values())==34
attributed=set()
for i, edge in enumerate(edges):
    for lo,hi,_,_,_,name in interval_costs(edge,combined,snaps.get(i,())):
        if hi>lo:
            attributed.add(name)
assert attributed==names
for name, table in [('verified',original),('estimated',stations)]:
    with (folder/f'coverage-{name}.pkl').open('rb') as f:
        tiles=pickle.load(f)
    assert all(g.is_valid for _,g,_ in tiles)
    assert all(c.difference(city.buffer(.005)).is_empty and r.difference(city.buffer(.005)).is_empty
               for _,c,r in tiles)
    print(name, len(tiles),round(sum(c.area for _,c,_ in tiles)/1e6,2),
          round(sum(r.length for _,_,r in tiles)/1e3,2))
ns = {'svg':'http://www.w3.org/2000/svg'}
root = ElementTree.parse(folder/'wuxi-walk.svg').getroot()
ids = {item.get('id') for item in root.iter() if item.get('id')}
assert {'city-clip','center-clip','jiangyin-clip','wuxi-land','walk-area','walk-roads',
        'estimated-area','estimated-roads','district-areas'} <= ids
main = root.find("./svg:g[@clip-path='url(#city-clip)']", ns)
assert {e.get('data-station') for e in main.findall('svg:circle',ns) if e.get('data-station')}==names
assert {e.get('data-district') for e in main.findall('svg:text',ns) if e.get('data-district')}==DISTRICTS
hrefs = [item.get('href')[1:] for item in root.findall('.//svg:use',ns)]
assert not set(hrefs)-ids
print('Verified SVG panels, 89 contributing stations, 7 county-level divisions, two confidence layers and internal SVG references.')
