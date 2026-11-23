from math import floor,ceil
import argparse

from extract_imports import *
from coverage import approx_area, CELL
from city_stations import get_inputs
from city_routes import load_model
from route import STRtree

TILE = 8192

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--station')
    args = parser.parse_args()
    stamp,districts,points,ways,polygons,relations,coast,basemap = get_inputs()
    city,stations,edges,cut_geo,cut_kind,exit_edges,distances,seeds,contributions = load_model()
    active = [i for i,e in enumerate(edges) if e[0] in distances or e[1] in distances or i in exit_edges]
    line_geoms = [LineString([edges[i][2],edges[i][3]]) for i in active]
    route_tree = STRtree(line_geoms)
    cut_tree = STRtree(cut_geo)
    polygon_trees = {kind:STRtree([g for _,_,g in polygons[kind]]) for kind in ('water','restricted','building')}
    tiles = set()
    for a in line_geoms:
        x1,y1,x2,y2 = a.bounds
        for x in range(floor((x1-50)/TILE),floor((x2+50)/TILE)+1):
            for y in range(floor((y1-50)/TILE),floor((y2+50)/TILE)+1):
                tiles.add((x,y))
    output = []
    if args.station:
        affected = shapely.union_all([Point(xy).buffer(1080) for _,xy,_,_ in stations[args.station]['exits']])
        assert not affected.is_empty
        with (work/'city-coverage.pkl').open('rb') as f:
            output = [entry for entry in pickle.load(f) if not affected.intersects(box(*entry[0]))]
    for x,y in sorted(tiles):
        tile = box(x*TILE,y*TILE,(x+1)*TILE,(y+1)*TILE)
        if args.station and not affected.intersects(tile):
            continue
        show = tile.intersection(city)
        if show.is_empty:
            continue
        wide = tile.buffer(120)
        local_ids = [active[i] for i in route_tree.query(wide,predicate='intersects')]
        local_edges = [edges[i] for i in local_ids]
        if not local_edges:
            continue
        local_exit_edges = {i:exit_edges[j] for i,j in enumerate(local_ids) if j in exit_edges}
        cut_ids = cut_tree.query(wide,predicate='intersects')
        local_polys = {kind:[polygons[kind][i] for i in tree.query(wide,predicate='intersects')] for kind,tree in polygon_trees.items()}
        area,roads = approx_area(tile,local_polys,local_edges,[cut_geo[i] for i in cut_ids],
                                 [cut_kind[i] for i in cut_ids],local_exit_edges,distances,minimum_area=0,report=False)
        area = area.intersection(show)
        roads = roads.intersection(show)
        if not area.is_empty or not roads.is_empty:
            output.append((tile.bounds,area,roads))
        print('Tile',x,y,'km²',round(area.area/1e6,2),'route-km',round(roads.length/1e3,1),flush=True)
    total_area = sum(g.area for _,g,_ in output)
    total_roads = sum(g.length for _,_,g in output)
    print('Tile count',len(output),'area km²',round(total_area/1e6,2),'route km',round(total_roads/1e3,1),flush=True)
    assert 100e6<total_area<600e6
    with (work/'city-coverage.pkl').open('wb') as f:
        pickle.dump(output,f,protocol=5)
