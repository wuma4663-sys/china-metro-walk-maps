from pathlib import Path
import re

import osmium

from stations import projection


ROOT = Path(__file__).resolve().parent
LINE_STATIONS = {
    1: '路窝 杏山子 韩山 工农路 人民广场 苏堤路 徐医附院 彭城广场 民主北路 徐州火车站 子房山 铜山路 黄山垅 庆丰路 医科大学 乔家湖 金龙湖 徐州东站'.split(),
    2: '客运北站 李沃 九里山 奔腾大道 九龙湖 庆云桥 彭城广场 户部山 师大云龙校区 中心医院 淮塔 科技城 七里沟 百果园 拖龙山 大龙湖 市行政中心 汉源大道 新元大道 新城区东'.split(),
    3: '银山 高新区南 钱江路 焦山 浦江路 无名山公园 玉泉河 师范大学 翟山 南三环路 矿大文昌校区 淮塔 和平大桥 天桥 徐州火车站 白云山 下淀 杨庄 金山桥 经贸学校 蟠桃 振兴大道'.split(),
    6: '铜山中医院 玉泉河 高家营 驿城 检测园 塘坊 市中医院 迎宾大道 丽水路 市行政中心 一中南 奥体中心 博览中心 赵武 大湖 徐州东站'.split(),
}
COUNTIES = {
    '320302': '鼓楼区', '320303': '云龙区', '320305': '贾汪区', '320311': '泉山区', '320312': '铜山区',
    '320321': '丰县', '320322': '沛县', '320324': '睢宁县', '320381': '新沂市', '320382': '邳州市',
}
STATION_NAMES = {name for names in LINE_STATIONS.values() for name in names}
NETWORK_EXTENT = (117.02, 34.10, 117.37, 34.37)
CITY_EXTENT = (115.70, 33.58, 118.72, 35.13)


def inside(lon, lat, extent=NETWORK_EXTENT):
    west, south, east, north = extent
    return west <= lon <= east and south <= lat <= north


def station_name(tags):
    return re.sub(r'[（(]\d+号线[）)]$', '', tags.get('name:zh') or tags.get('name') or '').strip()


def station_coordinates(source):
    centers, routes = {}, {}
    for node in osmium.FileProcessor(str(source)).with_filter(osmium.filter.EntityFilter(osmium.osm.NODE)):
        tags = node.tags
        if not node.location.valid() or tags.get('railway') not in {'station', 'stop'} or not inside(node.lon, node.lat):
            continue
        name = station_name(tags)
        if name in STATION_NAMES and (tags.get('station') == 'subway' or tags.get('subway') == 'yes' or tags.get('railway') == 'stop'):
            centers[node.id] = (name, node.lon, node.lat, tags.get('public_transport') == 'station')

    for relation in osmium.FileProcessor(str(source)).with_filter(osmium.filter.EntityFilter(osmium.osm.RELATION)):
        tags = relation.tags
        ref = tags.get('ref', '')
        if tags.get('route') != 'subway' or ref not in {'1', '2', '3', '6'}:
            continue
        identifiers = [m.ref for m in relation.members if m.type == 'n' and m.ref in centers]
        if not identifiers:
            continue
        line = int(ref)
        if not set(LINE_STATIONS[line]) & {centers[i][0] for i in identifiers}:
            continue
        routes.setdefault(line, []).append((relation.id, identifiers, [m.ref for m in relation.members if m.type == 'w' and not m.role.startswith('platform')]))

    candidates = {}
    for line, names in LINE_STATIONS.items():
        for name in names:
            on_route = [centers[i] for _, nodes, _ in routes.get(line, []) for i in nodes if centers[i][0] == name]
            namesake = [entry for entry in centers.values() if entry[0] == name]
            options = on_route or namesake
            if options:
                _, lon, lat, _ = max(options, key=lambda entry: entry[-1])
                candidates[line, name] = (lon, lat)
    missing = [(line, name) for line, names in LINE_STATIONS.items() for name in names if (line, name) not in candidates]
    if missing:
        raise ValueError(f'Missing station coordinates: {missing}')
    return candidates, routes


if __name__ == '__main__':
    import sys

    source = Path(sys.argv[1])
    candidates, routes = station_coordinates(source)
    for line, names in LINE_STATIONS.items():
        print(line, len(names), [(r, len(n), len(w)) for r, n, w in routes.get(line, [])])
        for name in names:
            print(name, candidates[line, name])
