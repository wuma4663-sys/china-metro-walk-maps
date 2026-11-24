import heapq
import math

from extract_imports import *
from stations import real_stations
from shapely.strtree import STRtree

LIMIT = 1000
PRIVATE = {'no','private','customers','military','permit','delivery','employees','agricultural','forestry'}
FOOT = {'yes','designated','permissive','official'}
ROADS = {'footway','pedestrian','living_street','steps','path','corridor','elevator','residential','service',
         'unclassified','tertiary','secondary','primary','track','road'}
PEDESTRIAN = {'footway','pedestrian','steps','path','corridor','elevator'}
DIVIDED = {'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link'}
FENCES = {'fence','wall','retaining_wall','hedge','city_wall','ditch','guard_rail','jersey_barrier'}
INACCESSIBLE = FENCES | {'block','turnstile','full-height_turnstile','cattle_grid','bollard_row'}


def permission(t):
    f = t.get('foot')
    if f in PRIVATE:
        return False
    if f in FOOT:
        return True
    return t.get('access') not in PRIVATE and t.get('access:conditional','').split('@')[0].strip() not in {'private','no'}


def allowed(t):
    h = t.get('highway')
    if not h or h in {'construction','proposed','abandoned','razed','disused','raceway','busway','bus_guideway','motorway','motorway_link'}:
        return False
    if t.get('motorroad') == 'yes' or t.get('sac_scale') in {'difficult_alpine_hiking','demanding_alpine_hiking','alpine_hiking'}:
        return False
    if not permission(t):
        return False
    if t.get('foot') in FOOT or h in PEDESTRIAN:
        return True
    if t.get('sidewalk') == 'separate' or (
        t.get('sidewalk:left') == 'separate' and t.get('sidewalk:right') in {'separate','no','none'}
    ) or (t.get('sidewalk:right') == 'separate' and t.get('sidewalk:left') in {'separate','no','none'}):
        return False
    if t.get('sidewalk') in ('both','yes','left','right') or any(
        t.get(f'sidewalk:{side}') in ('yes','both') for side in ('left','right','both')
    ):
        return True
    if h in {'primary','secondary'} and t.get('sidewalk') in {'no','none'}:
        return False
    if t.get('service') in {'drive-through','emergency_access'}:
        return False
    return h in ROADS


def directions(t):
    val = t.get('oneway:foot')
    return val != '-1', val not in ('yes','1','true')


def ground(t):
    try:
        layer = float(t.get('layer','0'))
    except ValueError:
        layer = 0
    return (not layer and t.get('bridge','no') == 'no' and t.get('tunnel','no') == 'no' and
            t.get('indoor') != 'yes' and t.get('level','0') in {'0','0;1'})


def base_nearby(district, ways, areas):
    context = box(*district.bounds).buffer(2600)
    dx, dy, ex, ey = context.bounds
    geometry = []
    for identifier, t, ids, coordinates in ways:
        if not any(dx<=x<=ex and dy<=y<=ey for x,y in coordinates):
            continue
        if allowed(t) or t.get('highway') in DIVIDED | {'tertiary'} or t.get('railway') or t.get('barrier') or t.get('waterway'):
            geometry.append((identifier,t,ids,coordinates))
    area_layers = defaultdict(list)
    for kind, ident, tags, geom in areas:
        if shapely.intersects(context,geom):
            area_layers[kind].append((ident,tags,geom if geom.is_valid else shapely.make_valid(geom)))
    return geometry, area_layers


def construct(district, points, features):
    envelope = district.buffer(1150)
    shapely.prepare(envelope)
    edges = []
    junctions = defaultdict(list)
    cuts, cut_geo, cut_kind = [], [], []
    blocked = {i for i,(_,_,t) in points.items() if not permission(t) or
               (t.get('barrier') in INACCESSIBLE and t.get('foot') not in FOOT)
               or (t.get('barrier') in {'gate','lift_gate','swing_gate'} and t.get('locked')=='yes')}
    # Split access-blocking nodes by way so barriers do not become transfer points.
    for way_id,t,refs,coords in features:
        walk = allowed(t)
        on_ground = ground(t)
        fwd, rev = directions(t)
        cl = t.get('highway','')
        if on_ground:
            if t.get('barrier') in FENCES and t.get('access') not in FOOT:
                cut_geo.append(LineString(coords))
                cut_kind.append('barrier')
            if (cl in DIVIDED or t.get('railway') in {'rail','subway','light_rail','narrow_gauge','construction'}
                    or t.get('waterway') in {'river','canal','stream','ditch','drain'}):
                cut_geo.append(LineString(coords))
                cut_kind.append('road' if cl in DIVIDED else 'other')
        if not walk:
            continue
        # Give walking plazas mapped as a closed highway their regular network perimeter.
        for ia,ib,xy1,xy2 in zip(refs,refs[1:],coords,coords[1:]):
            if not (shapely.intersects_xy(envelope,*xy1) or shapely.intersects_xy(envelope,*xy2)):
                continue
            if ia in blocked:
                ia = (way_id, ia, len(edges))
            if ib in blocked:
                ib = (way_id, ib, len(edges)+1)
            length = hypot(xy2[0]-xy1[0],xy2[1]-xy1[1])
            if length < 0.001 and cl != 'elevator':
                continue
            length = max(length, 0.5) if cl == 'elevator' else length
            edge_num = len(edges)
            edges.append((ia,ib,xy1,xy2,length,fwd,rev,on_ground,cl,way_id))
            junctions[ia].append((edge_num,1))
            junctions[ib].append((edge_num,0))
    return edges,junctions,cut_geo,cut_kind


def connect_stations(district, stations, points, edges, junctions, cut_geo, cut_kind, polygons, *, road_names=None):
    walk_geoms = [LineString([e[2],e[3]]) for e in edges]
    ground_ids = [i for i,e in enumerate(edges) if e[7] or e[8] in PEDESTRIAN]
    tree = STRtree([walk_geoms[i] for i in ground_ids])
    cut_tree = STRtree(cut_geo)
    building = [g for _,_,g in polygons['building']]
    building_names = [t.get('name','').removesuffix('站') for _,t,_ in polygons['building']]
    build_tree = STRtree(building)
    hard_features = [(kind,t.get('name'),g) for kind in ('water','restricted') for _,t,g in polygons[kind]]
    hard_areas = [g for _,_,g in hard_features]
    hard_tree = STRtree(hard_areas)
    seeds = {}
    from_edges = defaultdict(list)
    snapped = []
    component_size = {}
    visited = set()
    for ident in junctions:
        if ident in visited:
            continue
        found = [ident]
        visited.add(ident)
        for node in found:
            for ei,reverse in junctions[node]:
                neighbor = edges[ei][reverse]
                if neighbor not in visited:
                    visited.add(neighbor)
                    found.append(neighbor)
        component_size.update((node,len(found)) for node in found)
    def set_node(i,d,src):
        if d<=LIMIT and (i not in seeds or seeds[i][0]>d):
            seeds[i] = (d,src)

    for name,s in stations.items():
        s['matched'] = []
        for identifier,xy,ref,source in s['exits']:
            access_cost = s.get('access_costs',{}).get(identifier,0)
            pt = Point(xy)
            if district.distance(pt) > LIMIT or (identifier in points and (
                not permission(points[identifier][2]) or points[identifier][2].get('entrance') in {'exit','emergency'}
            )):
                continue
            if identifier in junctions:
                set_node(identifier,access_cost,name)
                s['matched'].append((xy,ref,source,access_cost))
                continue
            options = []
            radius = s.get('snap_radius',{'三鲁公路':104,'三林南':65,'莘庄':60,'春申路':112,
                      '望园路':82,'罗南新村':103,'长江西路':65}.get(name,55))
            radius = s.get('snap_radii',{}).get(identifier,radius)
            station_buildings = {name,*s.get('station_buildings',())}
            for ti in tree.query(pt,predicate='dwithin',distance=radius):
                ei = ground_ids[ti]
                a,b,xy1,xy2,length,fwd,rev,is_ground,cl,way_id = edges[ei]
                line = walk_geoms[ei]
                along = line.project(pt)
                position = line.interpolate(along)
                step = pt.distance(position)
                if step>55 and s.get('snap_way_ids') and way_id not in s['snap_way_ids']:
                    continue
                if step>55 and s.get('snap_roads') and (not road_names or road_names.get(way_id) not in s['snap_roads']):
                    continue
                bridge_snap = s.get('snap_elevated_ways',{}).get(way_id,8)
                if name=='莘庄' and ref.startswith('南') and cl in PEDESTRIAN:
                    bridge_snap = max(32,bridge_snap)
                if not is_ground and step > bridge_snap:
                    continue
                if step > .05:
                    path = LineString([xy,position.coords[0]])
                    # The operator identifies exits 2/3 on these streets. The public
                    # station approach can cross the encompassing access polygon.
                    public_station_path = (road_names and name=='长江西路' and ref in {'2','3'}
                                           and road_names.get(way_id) in {'长江西路','郁江巷路'})
                    if any(path.relate_pattern(hard_areas[i], 'T********') and not (
                        public_station_path and hard_features[i][:2]==('restricted','后工业生态景观公园')
                    ) for i in hard_tree.query(path)):
                        continue
                    if any(path.intersection(cut_geo[i]).distance(position) > 2.0
                           for i in cut_tree.query(path,predicate='crosses')):
                        continue
                    if any((crossing:=path.intersection(building[i]).length) > 2 and
                           not (building_names[i] in station_buildings and building[i].distance(pt)<5 and crossing<=6) and
                           (not building[i].covers(pt) or crossing>(42 if building_names[i] in station_buildings else 20))
                           for i in build_tree.query(path)):
                        continue
                disconnected_penalty = (80 if name=='春申路' else 34 if source=='百度地图' else 0) if component_size[a]<30 else 0
                rank = step + disconnected_penalty + (0 if cl in PEDESTRIAN else 6 if cl not in DIVIDED else 14)
                options.append((rank,step,ei,along,position.coords[0]))
            if not options:
                print('UNMATCHED',name,ref,source,tuple(round(q,1) for q in xy),flush=True)
                continue
            _,step,ei,along,position = min(options)
            if step>55:
                step += 18
            step += access_cost
            a,b,_,_,length,fwd,rev,*_ = edges[ei]
            if fwd:
                set_node(a,step+along,name)
            if rev:
                set_node(b,step+length-along,name)
            from_edges[ei].append((along,step,name))
            s['matched'].append((xy,ref,source,round(step,1)))
            if step>.05:
                snapped.append((xy,position))
    return seeds,from_edges,snapped


def walk_distances(edges,junctions,seeds):
    distance = seeds.copy()
    queue = [(d,k,i) for k,(i,(d,name)) in enumerate(seeds.items())]
    heapq.heapify(queue)
    stamp = len(queue)
    while queue:
        d,_,i = heapq.heappop(queue)
        best, source = distance[i]
        if d!=best:
            continue
        for ei,reverse in junctions[i]:
            a,b,_,_,length,fwd,rev,*_ = edges[ei]
            if (reverse and not rev) or (not reverse and not fwd):
                continue
            next_id = b if reverse else a
            nd = d+length
            if nd<=LIMIT and nd<distance.get(next_id,(math.inf,None))[0]:
                distance[next_id] = (nd,source)
                heapq.heappush(queue,(nd,stamp,next_id))
                stamp += 1
    return distance


def interval_costs(edge, distance, extras):
    a,b,_,_,length,fwd,rev,*_ = edge
    costs = []
    if rev and a in distance:
        costs.append((0,min(length,LIMIT-distance[a][0]),0,distance[a][0],1,distance[a][1]))
    if fwd and b in distance:
        costs.append((max(0,length-LIMIT+distance[b][0]),length,length,distance[b][0],-1,distance[b][1]))
    for along,step,source in extras:
        if fwd:
            costs.append((max(0,along-LIMIT+step),along,along,step,-1,source))
        if rev:
            costs.append((along,min(length,along+LIMIT-step),along,step,1,source))
    return costs


def merged_intervals(costs):
    result = []
    for start, end in sorted((v[0],v[1]) for v in costs if v[1]>v[0]):
        if result and start<=result[-1][1]:
            result[-1] = (result[-1][0],max(end,result[-1][1]))
        else:
            result.append((start,end))
    return result


if __name__ == '__main__':
    source_date, points, ways, areas, relations, _ = read()
    district = next(g for kind, _, _, g in areas if kind=='district')
    stations = real_stations(points,ways,relations,district)
    features, polygons = base_nearby(district,ways,areas)
    edges,junctions,cut_geo,cut_kind = construct(district,points,features)
    print('Road edges',len(edges),'junctions',len(junctions),flush=True)
    seeds,exit_edges,snapped = connect_stations(district,stations,points,edges,junctions,cut_geo,cut_kind,polygons)
    distances = walk_distances(edges,junctions,seeds)
    contributions = defaultdict(set)
    for i,edge in enumerate(edges):
        a,b,xy1,xy2,length,*_ = edge
        if a not in distances and b not in distances and i not in exit_edges:
            continue
        for s,e,origin,cost,sign,name in interval_costs(edge,distances,exit_edges.get(i,())):
            if e>s and district.intersects(LineString([tuple(np.add(xy1,np.multiply(np.subtract(xy2,xy1),p/length))) for p in (s,e)])):
                contributions[name].add(i)
    print('Seeds',len(seeds),'Reached nodes',len(distances),'Contributing stations',len(contributions),flush=True)
    for name, s in stations.items():
        if s['matched'] or district.distance(Point(s['xy']))<1050:
            print(name,len(s['matched']),len(contributions[name]),[(r,o,d) for _,r,o,d in s['matched']],flush=True)
    with (work/'routes.pkl').open('wb') as f:
        pickle.dump((source_date,district,stations,features,polygons,edges,cut_geo,cut_kind,exit_edges,distances,dict(contributions),snapped),f,protocol=5)
    with (work/'seeds.pkl').open('wb') as f:
        pickle.dump(seeds,f,protocol=5)
