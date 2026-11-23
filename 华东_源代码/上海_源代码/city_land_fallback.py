import struct

from extract_imports import *
from city_stations import get_inputs
from city_coast import DISPLAY_EXTENT,land_within
from stations import projection
from coverage import pieces

extent = box(281000,3391000,435000,3533000)
lonlat_view = box(120.68,30.59,122.35,31.93)


def shoreline_from_shapefile(shp):
    region = []
    with shp.open('rb') as f:
        f.read(100)
        while head:=f.read(8):
            _,content_len=struct.unpack('>ii',head)
            raw=f.read(content_len*2)
            if struct.unpack_from('<i',raw)[0]!=5:
                continue
            bounds=box(*struct.unpack_from('<4d',raw,4))
            if not bounds.intersects(lonlat_view):
                continue
            n_parts,n_points=struct.unpack_from('<2i',raw,36)
            part_indices=np.frombuffer(raw,dtype='<i4',count=n_parts,offset=44)
            values=np.frombuffer(raw,dtype='<f8',count=2*n_points,offset=44+4*n_parts).reshape(n_points,2)
            rings = []
            for i,j in zip(part_indices,[*part_indices[1:],n_points]):
                xy = values[int(i):int(j),:]
                if len(xy)<4:
                    continue
                poly = Polygon(xy)
                if poly.intersects(lonlat_view):
                    rings.append((shapely.is_ccw(poly.exterior),poly))
            outer = shapely.union_all([p for ccw,p in rings if not ccw])
            inner = shapely.union_all([p for ccw,p in rings if ccw])
            if not outer.is_empty:
                region.append(outer.difference(inner).intersection(lonlat_view))
    return shapely.transform(shapely.union_all(region),projection.transform,interleaved=False).intersection(extent)


if __name__=='__main__':
    _,_,_,_,_,_,coast,_ = get_inputs()
    # Natural Earth provides land polygons where the local OSM extract has open coastline chains.
    natural = shoreline_from_shapefile(next((work/'ne-land').glob('*.shp')))
    patches, _ = land_within(coast,extent)
    # Retain complete small OSM islands alongside the generalized mainland.
    islands = [p for p in pieces(patches,'Polygon') if 200<p.area<5e7 and not p.touches(extent.boundary)]
    land=shapely.union_all([natural,*islands])
    print('Land polygons',len(list(pieces(land,'Polygon'))),'km²',round(land.area/1e6,1),flush=True)
    for name,lon_lat in {'Shanghai':(121.48,31.21),'Chongming':(121.53,31.63),'Changxing':(121.68,31.39),
                         'Hengsha':(121.86,31.35),'estuary':(121.72,31.56),'East Sea':(122.2,31.01),'Pudong Airport':(121.801,31.145)}.items():
        print(name,land.covers(Point(projection.transform(*lon_lat))),flush=True)
    with (work/'city-final-land.pkl').open('wb') as f:
        pickle.dump((land,'Natural Earth 1:10m and OpenStreetMap coastlines'),f)
