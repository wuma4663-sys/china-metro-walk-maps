from common import *
from coverage import pieces
from route_suzhou import load_routes
from route import LIMIT
from lxml import etree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

stamp,districts,_,_,areas,_,_,_=read_model()
city,stations,edges,_,_,_,known,seeds,_=load_routes()
with (folder/'coverage.pkl').open('rb') as f:
    tiles=pickle.load(f)

nodes,positions,arc={},{},{}


def add(a,b,weight):
    arc[a,b]=min(weight,arc.get((a,b),np.inf))


for a,b,p,q,length,forward,reverse,*_ in edges:
    ia=nodes.setdefault(a,len(nodes))
    ib=nodes.setdefault(b,len(nodes))
    positions[a],positions[b]=p,q
    if forward:
        add(ib,ia,length)
    if reverse:
        add(ia,ib,length)
super_source=len(nodes)
for node,(weight,_) in seeds.items():
    add(super_source,nodes[node],weight)
ij=np.asarray(list(arc))
sp=coo_matrix((list(arc.values()),(ij[:,0],ij[:,1])),shape=(super_source+1,super_source+1)).tocsr()
numerical=dijkstra(sp,indices=super_source,limit=1310)
assert abs(int(sum(numerical<=LIMIT-1e-7))-1-len(known))<=1
assert max(abs(numerical[nodes[n]]-d) for n,(d,_) in known.items())<1e-6
print('Verified shortest path distances for',len(known),'reachable graph nodes',flush=True)

clip=city.buffer(.04)
shapely.prepare(clip)
assert all(a.is_valid and clip.covers(a) for _,a,_ in tiles)
painted=sum(a.area for _,a,_ in tiles)/1e6
walked=sum(g.length for _,_,g in tiles)/1000
assert painted>75 and walked>1400
model_exits=[position for station in stations.values() for position,_,_,_ in station['matched']]
spatial=cKDTree(model_exits)
witness=None
for n,i in nodes.items():
    if not 1160<numerical[i]<1230:
        continue
    p=Point(positions[n])
    radius=spatial.query(positions[n])[0]
    if 500<radius<910 and city.covers(p) and not any(a.covers(p) for _,a,_ in tiles):
        witness=round(float(radius)),round(float(numerical[i]))
        break
assert witness is not None
print('Excluded model detour, metres straight-line and on network:',witness,flush=True)
major_water=shapely.union_all([g for _,_,g in areas['water'] if g.area>1e6]).buffer(-12)
from shapely.geometry import MultiPolygon
wet=0
for bounds,area,_ in tiles:
    if area.is_empty:
        continue
    lake=major_water.intersection(box(*bounds))
    if lake.is_empty:
        continue
    dry_shape=area if area.geom_type in {'Polygon','MultiPolygon'} else MultiPolygon(list(pieces(area,'Polygon')))
    wet_shape=lake if lake.geom_type in {'Polygon','MultiPolygon'} else MultiPolygon(list(pieces(lake,'Polygon')))
    wet+=dry_shape.intersection(wet_shape,grid_size=.05).area
assert wet<150,wet

doc=etree.parse(str(folder/'suzhou-walk.svg'))
assert set(doc.xpath('//@data-district'))==DISTRICTS
assert len(doc.xpath('//*[@id="district-areas"]/*'))==len(DISTRICTS)
assert not doc.xpath('//*[local-name()="image" or local-name()="script"]')
assert len(doc.xpath('//*[@id="walk-area"]/*'))>=10
print('Verified nine district and county-level city boundaries; vector-only SVG.',flush=True)
print('Coverage',round(painted,2),'km², reachable roads',round(walked,1),'km; water interior overlap',round(wet,1),'m²',flush=True)
print('Unconnected stations in city:',[name for name,s in stations.items() if not s['matched'] and city.covers(Point(s['xy']))],flush=True)
print('Model access points:',len(model_exits),'distinct matched stations:',sum(bool(s['matched']) for s in stations.values()),flush=True)
