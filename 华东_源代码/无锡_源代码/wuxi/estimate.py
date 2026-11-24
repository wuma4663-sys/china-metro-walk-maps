from common import *
from route_wuxi import load_routes
from route import STRtree, PEDESTRIAN, DIVIDED, walk_distances, interval_costs

_, districts, nodes, ways, areas, _, _, _ = read_model()
city, stations, edges, cut_geo, cut_kind, snaps, distances, seeds, contribution = load_routes()
walk_segments = [LineString(e[2:4]) for e in edges]
segment_index = STRtree(walk_segments)
hard_areas = [g for k in ('water','restricted') for _,_,g in areas[k]]
area_index = STRtree(hard_areas)
barriers = [g for g,k in zip(cut_geo,cut_kind) if k in {'barrier','other'}]
barrier_index = STRtree(barriers)
junctions = defaultdict(list)
for index, (a,b,*_) in enumerate(edges):
    junctions[a].append((index, True))
    junctions[b].append((index, False))

# Use known station-adjacent public approaches where available.
# Edge ids are OSM way ids in the verified road snapshot.
known = {
    '中山公园': {744523157, 1080533081},
    '江阴外滩': {415272730, 121186343},
    '无锡火车站': {1266567006, 1266566983},
    '无锡东站': {302555975},
    '硕放机场': {736409580, 165144933},
}

supplemental_seeds = {}
supplemental_snaps = defaultdict(list)
for name,station in stations.items():
    if station['matched']:
        continue
    p=Point(station['xy'])
    candidates=[]
    for index in segment_index.query(p,predicate='dwithin',distance=300):
        edge = edges[index]
        a,b,_,_,length,fwd,rev,at_grade,kind,way_id = edge
        if not at_grade or kind in {'track','motorway','trunk','elevator','corridor'}:
            continue
        segment = walk_segments[index]
        along = segment.project(p)
        location = segment.interpolate(along)
        distance=p.distance(location)
        if distance > 215 and way_id not in known.get(name, ()):
            continue
        if distance > .05:
            approach = LineString([p,location])
            if any(approach.relate_pattern(hard_areas[i], 'T********')
                   and approach.intersection(hard_areas[i]).length > 2
                   for i in area_index.query(approach)):
                continue
            if any(approach.crosses(barriers[i])
                   and approach.intersection(barriers[i]).distance(p)>5
                   and approach.intersection(barriers[i]).distance(location)>3
                   for i in barrier_index.query(approach)):
                continue
        rank=distance+(0 if kind in PEDESTRIAN else 22 if kind in DIVIDED else 10)
        if name in known and way_id in known[name]:
            rank-=50
        if len(junctions[a])+len(junctions[b]) <= 3:
            rank+=14
        candidates.append((rank,distance,int(index),along,location))
    if not candidates:
        print('No plausible public connection',name,flush=True)
        continue
    _,distance,index,along,location = min(candidates, key=lambda item:item[:4])
    a,b,_,_,length,fwd,rev,*_ = edges[index]
    cost = round(1.15*distance+30,1)
    if fwd:
        entry = (cost+along,name)
        if entry[0] < supplemental_seeds.get(a,(float('inf'),''))[0]:
            supplemental_seeds[a] = entry
    if rev:
        entry = (cost+length-along,name)
        if entry[0] < supplemental_seeds.get(b,(float('inf'),''))[0]:
            supplemental_seeds[b] = entry
    supplemental_snaps[index].append((along,cost,name))
    station['estimated'] = True
    station['matched'].append((location.coords[0],'','站口接驳估算',cost))
    print('Estimated',name,'way',edges[index][-1],edges[index][8],round(distance),cost,flush=True)

estimated = walk_distances(edges,junctions,supplemental_seeds)
combined = distances.copy()
for idx, entry in estimated.items():
    if idx not in combined or entry[0]<combined[idx][0]:
        combined[idx]=entry
both = {i:[*snaps.get(i,()),*supplemental_snaps.get(i,())] for i in snaps.keys()|supplemental_snaps.keys()}
counts=Counter()
for idx,edge in enumerate(edges):
    if edge[0] in estimated or edge[1] in estimated or idx in supplemental_snaps:
        for lo,hi,_,_,_,name in interval_costs(edge,estimated,supplemental_snaps.get(idx,())):
            if hi>lo:
                counts[name]+=1
print('Estimated stations',sum(s.get('estimated',False) for s in stations.values()),flush=True)
print('Small estimated networks',[(name,counts[name]) for name,s in stations.items() if s.get('estimated') and counts[name]<35],flush=True)
print('No modeled access',[name for name,s in stations.items() if not s['matched']],flush=True)
with (folder/'augmented.pkl').open('wb') as f:
    pickle.dump((stations,combined,both,estimated,supplemental_snaps),f,protocol=5)


