from collections import Counter, defaultdict
import pickle

from network import ROOT, STATION_NAMES
from route import connect_stations, construct, interval_costs, walk_distances
from station_approaches import add_estimated_approaches
from stations import real_stations


def load_extract():
    with (ROOT / 'extract-xuzhou.pkl').open('rb') as stream:
        return pickle.load(stream)


def load_routes():
    with (ROOT / 'routes-xuzhou.pkl').open('rb') as stream:
        return pickle.load(stream)


def route():
    stamp, boundaries, points, ways, polygons, relations, municipality, basemap, station_data, centers = load_extract()
    city = municipality[1]
    supplements = [ROOT / 'confirmed-exits.json']
    stations = real_stations(points, ways, relations, city, map_data=station_data,
                             supplemental_files=supplements, hub_access_enabled=False, max_entrance_distance=335)
    if set(stations) != STATION_NAMES:
        raise ValueError(f'Station roster mismatch: {STATION_NAMES ^ stations.keys()}')
    names = {oid: tags['name'] for oid, tags, _, _ in ways if tags.get('highway') and tags.get('name')}
    edges, junctions, cuts, cut_kinds = construct(city, points, ways)
    print('Walking graph', len(edges), 'edges and', len(junctions), 'nodes', flush=True)
    official_seeds, official_snaps, _ = connect_stations(city, stations, points, edges, junctions, cuts, cut_kinds, polygons, road_names=names)
    seeds = official_seeds.copy()
    snaps = defaultdict(list, {edge: list(positions) for edge, positions in official_snaps.items()})
    estimated = add_estimated_approaches(stations, centers, edges, junctions, polygons, cuts, cut_kinds, seeds, snaps)
    distances = walk_distances(edges, junctions, seeds)
    official_distances = walk_distances(edges, junctions, official_seeds)
    contribution = Counter()
    for i, edge in enumerate(edges):
        if edge[0] in distances or edge[1] in distances or i in snaps:
            for start, end, _, _, _, name in interval_costs(edge, distances, snaps.get(i, ())):
                if start < end:
                    contribution[name] += 1
    for name, station in stations.items():
        print(name, len(station['exits']), len(station['matched']), contribution[name], flush=True)
    print('Unrouted:', [name for name, s in stations.items() if not s['matched']], flush=True)
    print('Estimated approaches:', len(estimated), sorted(estimated), flush=True)
    print('Reached:', len(distances), 'nodes via', sum(len(s['matched']) for s in stations.values()), 'entrances', flush=True)
    with (ROOT / 'routes-xuzhou.pkl').open('wb') as stream:
        pickle.dump((stations, edges, cuts, cut_kinds, snaps, distances, contribution, official_snaps, official_distances), stream, protocol=5)


if __name__ == '__main__':
    route()
