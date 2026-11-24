from math import floor
import pickle

from shapely.geometry import GeometryCollection, LineString, box
from shapely.strtree import STRtree

from coverage import approx_area
from network import ROOT
from route import LIMIT, interval_costs
from route_xuzhou import load_extract, load_routes


TILE = 4096


def tiles():
    _, _, _, _, areas, _, municipality, _, _, _ = load_extract()
    city = municipality[1]
    stations, edges, cuts, cut_kinds, snaps, distances, _, verified_snaps, verified_distances = load_routes()
    active = [i for i, edge in enumerate(edges) if
              (edge[0] in distances or edge[1] in distances or i in snaps) and
              any(a < b for a, b, *_ in interval_costs(edge, distances, snaps.get(i, ())))]
    lines = [LineString((edges[i][2], edges[i][3])) for i in active]
    roads_index = STRtree(lines)
    cuts_index = STRtree(cuts)
    area_index = {kind: STRtree([geom for _, _, geom in areas[kind]]) for kind in ('water', 'restricted', 'building')}
    used = set()
    for line in lines:
        a, b, c, d = line.bounds
        used.update((x, y) for x in range(floor((a - 50) / TILE), floor((c + 50) / TILE) + 1)
                    for y in range(floor((b - 50) / TILE), floor((d + 50) / TILE) + 1))

    result = []
    for x, y in sorted(used):
        tile = box(x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)
        city_tile = tile.intersection(city)
        if city_tile.is_empty:
            continue
        wide = tile.buffer(120)
        selected = [active[pos] for pos in roads_index.query(wide, predicate='intersects')]
        if not selected:
            continue
        entrance = {i: snaps[pos] for i, pos in enumerate(selected) if pos in snaps}
        obstructions = cuts_index.query(wide, predicate='intersects')
        clipped = {kind: [areas[kind][i] for i in tree.query(wide, predicate='intersects')] for kind, tree in area_index.items()}
        tile_edges = [edges[i] for i in selected]
        tile_cuts, tile_kinds = [cuts[i] for i in obstructions], [cut_kinds[i] for i in obstructions]
        surface, roads = approx_area(tile, clipped, tile_edges, tile_cuts, tile_kinds, entrance, distances, minimum_area=0, report=False)
        confirmed = {i: verified_snaps[pos] for i, pos in enumerate(selected) if pos in verified_snaps}
        if any(any(a < b for a, b, *_ in interval_costs(edge, verified_distances, confirmed.get(i, ()))) for i, edge in enumerate(tile_edges)):
            known_surface, known_roads = approx_area(tile, clipped, tile_edges, tile_cuts, tile_kinds, confirmed,
                                                   verified_distances, minimum_area=0, report=False)
        else:
            known_surface, known_roads = GeometryCollection(), GeometryCollection()
        surface, roads = surface.intersection(city_tile), roads.intersection(city_tile)
        if not surface.is_empty or not roads.is_empty:
            result.append((tile.bounds, surface, roads, known_surface.intersection(city_tile), known_roads.intersection(city_tile)))
    if not result or max(cost for cost, _ in distances.values()) > LIMIT:
        raise ValueError('Unexpected pedestrian coverage results')
    if any(not surface.is_valid or surface.difference(city).area > 0.01 for _, surface, *_ in result):
        raise ValueError('Invalid pedestrian area or municipal clip')
    print(f'Tiles {len(result)} · {sum(a.area for _, a, *_ in result) / 1e6:.2f} km² · '
          f'{sum(r.length for _, _, r, *_ in result) / 1000:.2f} km of roads', flush=True)
    with (ROOT / 'coverage-xuzhou.pkl').open('wb') as stream:
        pickle.dump(result, stream, protocol=5)


if __name__ == '__main__':
    tiles()
