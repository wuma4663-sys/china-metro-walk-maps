from math import hypot

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from route import PEDESTRIAN


# The station guide places both public exits south of 泉润大道 at 路窝.
# At 徐州东站 the published west/east plaza exits belong to separate approaches.
SIDE_LIMITS = {(1, '路窝'): (1, -1), (1, '徐州东站'): (0, -1), (6, '徐州东站'): (0, 1)}
EXTRA_APPROACHES = {(1, '杏山子'): 3, (1, '徐医附院'): 2, (6, '奥体中心'): 3}
# Use the mapped public street at the west plaza when the OSM paths within
# the station complex do not connect to the street graph.
HUB_PUBLIC_WAYS = {(1, '徐州东站'): {419176403, 1323386157}}


def component_sizes(edges, junctions):
    sizes = {}
    for node in junctions:
        if node in sizes:
            continue
        group, stack = {node}, [node]
        while stack:
            current = stack.pop()
            for index, reverse in junctions[current]:
                edge = edges[index]
                adjacent = edge[1] if reverse else edge[0]
                if adjacent not in group:
                    group.add(adjacent)
                    stack.append(adjacent)
        sizes.update((member, len(group)) for member in group)
    return sizes


def add_estimated_approaches(stations, centers, edges, junctions, polygons, cuts, cut_kinds, seeds, locations):
    sizes = component_sizes(edges, junctions)
    candidates = [index for index, edge in enumerate(edges) if edge[7] and edge[8] not in {'elevator', 'steps'}]
    geoms = [LineString((edges[index][2], edges[index][3])) for index in candidates]
    index = STRtree(geoms)
    obstacles = [geom for category in ('water', 'restricted') for _, _, geom in polygons[category]]
    obstacle_index = STRtree(obstacles)
    physical_cuts = [cut for cut, kind in zip(cuts, cut_kinds) if kind != 'road']
    cut_index = STRtree(physical_cuts)

    missing = [name for name, station in stations.items() if not station['matched']]
    estimates = set()
    for name in missing:
        used = []
        for (line, stop), center in centers.items():
            if stop != name or (used and name != '徐州东站' and min(hypot(center[0] - x, center[1] - y) for x, y in used) < 150):
                continue
            point = Point(center)
            radius = 310 if name == '徐州东站' else 245
            side = SIDE_LIMITS.get((line, name))
            ranked = []
            for pos in index.query(point, predicate='dwithin', distance=radius):
                edge_id = candidates[pos]
                a, b, _, _, length, forward, backward, _, road_class, way_id = edges[edge_id]
                segment = geoms[pos]
                along = segment.project(point)
                nearby = segment.interpolate(along)
                xy = nearby.x, nearby.y
                if side and (xy[side[0]] - center[side[0]]) * side[1] < 0:
                    continue
                offset = point.distance(nearby)
                if offset > .1:
                    connection = LineString((point, nearby))
                    if any(connection.intersection(obstacles[j]).length > 5 for j in obstacle_index.query(connection, predicate='intersects')):
                        continue
                    if way_id not in HUB_PUBLIC_WAYS.get((line, name), ()) and any(
                        connection.intersection(physical_cuts[j]).distance(point) > 12
                        for j in cut_index.query(connection, predicate='crosses')
                    ):
                        continue
                cost = max(30, offset + 18)
                rank = offset + (0 if road_class in PEDESTRIAN else 18 if road_class != 'service' else 28)
                if min(sizes[a], sizes[b]) < 22:
                    rank += 55
                ranked.append((rank, edge_id, along, cost, xy, length, forward, backward))
            accepted = 0
            for _, edge_id, along, cost, xy, length, forward, backward in sorted(ranked):
                if any(hypot(xy[0] - x, xy[1] - y) < 85 for x, y in used):
                    continue
                a, b = edges[edge_id][:2]
                for node, distance, allowed in ((a, cost + along, forward), (b, cost + length - along, backward)):
                    if allowed and distance < seeds.get(node, (1001, None))[0]:
                        seeds[node] = distance, name
                locations[edge_id].append((along, cost, name))
                stations[name]['matched'].append((xy, '', '站位估算', round(cost, 1)))
                used.append(xy)
                estimates.add(name)
                accepted += 1
                if accepted >= EXTRA_APPROACHES.get((line, name), 1):
                    break
    return estimates
