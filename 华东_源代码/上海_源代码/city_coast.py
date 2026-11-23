from extract_imports import *
from city_stations import get_inputs
from coverage import pieces
from shapely.strtree import STRtree
from shapely.geometry import MultiLineString
from shapely.ops import polygonize_full
from stations import projection

DISPLAY_EXTENT = (289000,3399000,435000,3516000)


def land_within(coast, viewport):
    original = [g for g in coast if viewport.intersects(g)]
    tree = STRtree(original)
    clipped = [g.intersection(viewport) for g in original]
    merged = shapely.union_all([viewport.boundary,*clipped],grid_size=.05)
    faces, cuts, dangles, invalid = polygonize_full(list(pieces(merged,'LineString')))
    dry = []
    for face in pieces(faces,'Polygon'):
        trial = face.representative_point()
        ref = original[tree.nearest(trial)]
        a = ref.project(trial)
        near = ref.interpolate(a)
        p = ref.interpolate(max(0,a-.5))
        q = ref.interpolate(min(ref.length,a+.5))
        is_land = (q.x-p.x)*(trial.y-near.y) - (q.y-p.y)*(trial.x-near.x) > 0
        if is_land and face.area>30:
            dry.append(face)
    return shapely.union_all(dry),dangles


if __name__=='__main__':
    stamp,districts,points,ways,polygons,relations,coast,basemap = get_inputs()
    view = box(*DISPLAY_EXTENT)
    land,dangling = land_within(coast,view)
    print('land',land.geom_type,land.area/1e6,'dangles km',dangling.length/1000)
    for key,(i,g) in districts.items():
        print(key,[(round(p.area/1e6,2),tuple(round(x) for x in p.bounds)) for p in sorted(pieces(g,'Polygon'),key=lambda x:-x.area)[:8]],
              round(land.intersection(g).area/1e6,2))
    for name,lon,lat in [('上海市区',121.48,31.21),('金山',121.22,30.76),('崇明',121.53,31.63),('长兴',121.68,31.39),
                         ('横沙',121.86,31.35),('长江口',121.72,31.56),('东海',122.2,31.01),('杭州湾',121.5,30.64),('青浦',121.10,31.14)]:
        print(name,view.covers(Point(projection.transform(lon,lat))),land.covers(Point(projection.transform(lon,lat))))
    with (work/'city-land.pkl').open('wb') as f:
        pickle.dump(land,f)
