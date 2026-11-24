from math import ceil, floor, sqrt

from PIL import Image, ImageDraw

from route import *
from shapely.geometry import MultiLineString

CELL = 8
END_STEPS = 4


def pieces(geometry, target):
    if geometry.is_empty:
        return
    if geometry.geom_type == target:
        yield geometry
    elif hasattr(geometry,'geoms'):
        for g in geometry.geoms:
            yield from pieces(g,target)


def make_shape(mask, x0, y0):
    active = {}
    rectangles = []
    height, width = mask.shape
    for i,line in enumerate(mask):
        cuts = np.flatnonzero(np.diff(np.pad(line,(1,1))))
        spans = {(int(a),int(b)) for a,b in zip(cuts[::2],cuts[1::2])}
        for span in active.keys()-spans:
            rectangles.append(box(x0+span[0]*CELL,y0-i*CELL,x0+span[1]*CELL,y0-active.pop(span)*CELL))
        for span in spans-active.keys():
            active[span] = i
    for span,row in active.items():
        rectangles.append(box(x0+span[0]*CELL,y0-height*CELL,x0+span[1]*CELL,y0-row*CELL))
    return shapely.union_all(rectangles)


def approx_area(district, polygons, edges, cut_geo, cut_kind, exit_edges, distances, *, minimum_area=1e6, report=True):
    dx,dy,ex,ey = district.bounds
    x0 = floor((dx-80)/CELL)*CELL
    y0 = ceil((ey+80)/CELL)*CELL
    width,height = ceil((ex+80-x0)/CELL),ceil((y0-dy+80)/CELL)
    seed = np.full((height,width),np.inf,np.float32)
    ground_features = []
    all_features = []
    bounds = box(x0,y0-height*CELL,x0+width*CELL,y0)
    inner = district.buffer(60)
    shapely.prepare(inner)
    max_seeded_cost = 0
    for ei, edge in enumerate(edges):
        a,b,xy1,xy2,length,fwd,rev,is_ground,cl,_ = edge
        if a not in distances and b not in distances and ei not in exit_edges:
            continue
        costs = interval_costs(edge,distances,exit_edges.get(ei,()))
        intervals = merged_intervals(costs)
        if not intervals:
            continue
        x1,y1 = xy1
        vx,vy = (xy2[0]-x1)/length,(xy2[1]-y1)/length
        for s,e in intervals:
            all_features.append(((x1+vx*s,y1+vy*s),(x1+vx*e,y1+vy*e)))
        if not is_ground or cl in {'elevator'}:
            continue
        if not (shapely.intersects_xy(inner,*xy1) or shapely.intersects_xy(inner,*xy2)):
            continue
        for s,e,origin,cost,sign,_ in costs:
            if e<s:
                continue
            t = np.linspace(s,e,max(2,ceil((e-s)/(CELL/3))+1))
            px,py = x1+vx*t,y1+vy*t
            xi,yi = np.floor((px-x0)/CELL).astype(int),np.floor((y0-py)/CELL).astype(int)
            ok = (xi>=0)&(yi>=0)&(xi<width)&(yi<height)
            xi,yi,t,px,py = xi[ok],yi[ok],t[ok],px[ok],py[ok]
            # Charge the local connection between the actual way and each cell center.
            dd = cost+(t-origin)*sign+np.hypot(x0+(xi+.5)*CELL-px,y0-(yi+.5)*CELL-py)
            np.minimum.at(seed,(yi,xi),dd)
    if not all_features:
        raise RuntimeError('No reachable road geometry')
    occupied = Image.new('L',(width,height),0)
    draw = ImageDraw.Draw(occupied)
    def pixel(coordinates):
        return [((x-x0)/CELL-.5,(y0-y)/CELL-.5) for x,y in coordinates]
    for kind in ('water','restricted','building'):
        for _,_,geom in polygons[kind]:
            if not bounds.intersects(geom):
                continue
            for p in pieces(geom,'Polygon'):
                if p.area<12 and kind=='building':
                    continue
                draw.polygon(pixel(p.exterior.coords),fill=1)
                for ring in p.interiors:
                    draw.polygon(pixel(ring.coords),fill=0)
    for line,kind in zip(cut_geo,cut_kind):
        if bounds.intersects(line):
            draw.line(pixel(line.coords),fill=1,width=1 if kind=='road' else 2)
    block = np.asarray(occupied).astype(bool)
    seed[block] = np.inf
    seed[seed>LIMIT] = np.inf
    min_cost = seed
    along = [(1,0,CELL),(-1,0,CELL),(0,1,CELL),(0,-1,CELL),
             (1,1,CELL*sqrt(2)),(1,-1,CELL*sqrt(2)),(-1,1,CELL*sqrt(2)),(-1,-1,CELL*sqrt(2))]
    def offby(n,d):
        return slice(max(0,d),min(n,n+d))
    for _ in range(END_STEPS):
        result = min_cost.copy()
        for dy,dx,length in along:
            sy,sx = offby(height,-dy),offby(width,-dx)
            ty,tx = offby(height,dy),offby(width,dx)
            transfer = min_cost[sy,sx]+length
            if dy and dx:
                viable = ~(block[ty,sx] | block[sy,tx])
                transfer[~viable] = np.inf
            np.minimum(result[ty,tx],transfer,out=result[ty,tx])
        result[block] = np.inf
        min_cost = result
    shown = min_cost<=LIMIT
    grid_geom = make_shape(shown,x0,y0)
    coverage = shapely.intersection(grid_geom,district)
    if not coverage.is_valid:
        coverage = shapely.make_valid(coverage)
    certified_roads = shapely.intersection(MultiLineString(all_features),district)
    if report:
        print('Map union area',round(coverage.area/1e6,3),'km²', 'Walkable within area',round(certified_roads.length/1e3,1),'km',flush=True)
    assert coverage.difference(district).area < .01 and coverage.area>=minimum_area
    assert np.all(min_cost[shown] <= LIMIT) and not np.any(shown & block)
    return coverage,certified_roads


if __name__ == '__main__':
    with (work/'routes.pkl').open('rb') as handle:
        source_date,district,stations,features,polygons,edges,cut_geo,cut_kind,exit_edges,distances,contributions,_ = pickle.load(handle)
    output = approx_area(district,polygons,edges,cut_geo,cut_kind,exit_edges,distances)
    with (work/'area.pkl').open('wb') as handle:
        pickle.dump(output,handle,protocol=5)
