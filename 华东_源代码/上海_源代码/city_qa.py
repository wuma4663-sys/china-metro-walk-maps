from extract_imports import *
from city_stations import get_inputs
from city_routes import load_model
from route import LIMIT
from coverage import pieces
from shapely.geometry import MultiPolygon
from lxml import etree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

_,districts,_,_,polys,_,_,_ = get_inputs()
city,stations,edges,_,_,_,known,seeds,_ = load_model()
with (work/'city-coverage.pkl').open('rb') as f:
    tiles=pickle.load(f)

indexed,xy,arcs = {},{},{}
def add(a,b,d):
    arcs[a,b]=min(d,arcs.get((a,b),np.inf))
for a,b,p,q,length,forward,reverse,*_ in edges:
    ia=indexed.setdefault(a,len(indexed))
    ib=indexed.setdefault(b,len(indexed))
    xy[a],xy[b]=p,q
    if forward:
        add(ib,ia,length)
    if reverse:
        add(ia,ib,length)
start=len(indexed)
for n,(cost,_) in seeds.items():
    add(start,indexed[n],cost)
ij=np.array(list(arcs))
m=coo_matrix((list(arcs.values()),(ij[:,0],ij[:,1])),shape=(start+1,start+1)).tocsr()
dist=dijkstra(m,indices=start,limit=1300)
assert sum(dist<=LIMIT-1e-6)-1 in (len(known),len(known)-1)
assert max(abs(dist[indexed[n]]-d) for n,(d,_) in known.items())<1e-6
print('Independent path distances verified:',len(known),flush=True)
city_tolerant = city.buffer(.02)
shapely.prepare(city_tolerant)
assert all(a.is_valid and city_tolerant.covers(a) for _,a,_ in tiles)
walk_km=sum(r.length for _,_,r in tiles)/1000
area_km=sum(a.area for _,a,_ in tiles)/1e6
assert 5000<walk_km<10000 and 150<area_km<350
covered_districts = set()
for name,(_,g) in districts.items():
    if any(a.intersection(g).area>0 for bounds,a,_ in tiles if box(*bounds).intersects(g)):
        covered_districts.add(name)
print('Districts without modeled coverage:',sorted(set(districts)-covered_districts),flush=True)
assert covered_districts==set(districts)-{'崇明区','金山区'}
water_area = shapely.union_all([g for _,_,g in polys['water'] if g.area>1e6]).buffer(-12)
wet_overlap = 0
for bounds,area,_ in tiles:
    cut_water = water_area.intersection(box(*bounds))
    wet_tile = cut_water if cut_water.geom_type in {'Polygon','MultiPolygon'} else MultiPolygon(list(pieces(cut_water,'Polygon')))
    fill_tile = area if area.geom_type in {'Polygon','MultiPolygon'} else MultiPolygon(list(pieces(area,'Polygon')))
    wet_overlap += fill_tile.intersection(wet_tile,grid_size=.05).area
print('Filled area in interior of major waters, square metres:',round(wet_overlap,2),flush=True)
assert wet_overlap<150
study_radius=cKDTree([xy for s in stations.values() for xy,_,_,_ in s['matched']])
found=None
for n,i in indexed.items():
    if 1190<dist[i]<1210:
        p=Point(xy[n])
        direct=study_radius.query(xy[n])[0]
        if 500<direct<940 and city.covers(p) and not any(a.covers(p) for _,a,_ in tiles):
            found=(round(direct),round(dist[i]))
            break
assert found is not None
doc=etree.parse(str(work/'shanghai-walk.svg'))
listed=doc.xpath('//@data-district')
assert set(listed)==set(districts) and len(listed)==16
assert len(doc.xpath('//*[@id="district-areas"]/*'))==16
assert len(doc.xpath('//*[@id="walk-area"]/*'))>=50
assert not doc.xpath('//*[local-name()="image" or local-name()="script"]')
outside=[name for name,s in stations.items() if not city.covers(Point(s['xy'])) and s['matched']]
missing=[name for name,s in stations.items() if city.covers(Point(s['xy'])) and not s['matched']]
print('Direct versus shortest network distance sample:',found)
print('Routable stations',sum(bool(s['matched']) for s in stations.values()),'outside city:',outside)
print('In-city station gaps:',missing)
print('Route-km',round(walk_km,1),'raster area km²',round(area_km,2))
print('Districts with coverage:',len(covered_districts))
print('SVG confirms all 16 district names and boundaries.')
