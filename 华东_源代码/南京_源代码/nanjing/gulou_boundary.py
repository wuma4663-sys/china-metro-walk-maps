"""Assemble Gulou's boundary with the ring order used in the published map."""

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import osmium
import shapely
from shapely.geometry import LineString
from shapely.ops import polygonize

from common import city_shape, folder, projection


def restore_gulou(snapshot):
    relation_id = 2139790
    roles = next(
        {member.ref: member.role for member in relation.members if member.type == "w"}
        for relation in osmium.FileProcessor(str(snapshot), osmium.osm.RELATION)
        if relation.id == relation_id
    )
    ways = (
        osmium.FileProcessor(str(snapshot), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations("flex_mem")
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
    )
    lines = defaultdict(list)
    for way in ways:
        if way.id in roles:
            coords = [projection.transform(node.lon, node.lat) for node in way.nodes]
            lines[roles[way.id]].append(LineString(coords))

    outer = shapely.union_all(list(polygonize(lines["outer"])))
    inner = shapely.union_all(list(polygonize(lines["inner"])))
    boundary = outer.difference(inner)
    output = folder / "extract.pkl"
    with output.open("rb") as handle:
        data = pickle.load(handle)
    districts = data[1]
    city = city_shape(districts, data[6])
    if not boundary.is_valid or not 45e6 < boundary.area < 72e6 or boundary.difference(city).area >= 1:
        raise ValueError("鼓楼区区界与发布版范围不符")
    districts["鼓楼区"] = (relation_id, boundary)
    with output.open("wb") as handle:
        pickle.dump(data, handle, protocol=5)


if __name__ == "__main__":
    restore_gulou(Path(sys.argv[1]))
