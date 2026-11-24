from datetime import datetime, timedelta, timezone
from html import escape
from math import ceil, floor
from pathlib import Path
import pickle

import shapely
from shapely.geometry import Point, box

from coverage import pieces
from network import ROOT, STATION_NAMES, projection
from route_xuzhou import load_extract, load_routes


WIDTH, HEIGHT = 1810, 1260
INK, MUTED, TEAL = '#1b3844', '#536970', '#244c5b'
CORAL, RED = '#fa806b', '#bf3e31'
ESTIMATE, ESTIMATE_ROADS = '#f6ca91', '#ac7543'
PAPER, LAND = '#faf9f5', '#fcfbf2'
ROAD_STYLES = {
    'street': ('#d4d8d0', 0, .53, 4),
    'minor': ('#d6d9d1', .43, .71, 7),
    'main': ('#bec9c7', .68, 1, 9),
    'rail': ('#a2b4bc', .6, .74, 9),
}
COUNTY_LABELS = {
    '丰县': (116.56, 34.66), '沛县': (116.88, 34.73), '铜山区': (117.04, 34.41), '贾汪区': (117.47, 34.46),
    '泉山区': (117.12, 34.27), '鼓楼区': (117.30, 34.29), '云龙区': (117.28, 34.22),
    '邳州市': (117.88, 34.40), '睢宁县': (117.87, 33.94), '新沂市': (118.42, 34.25),
}
DETAIL_LABELS = {
    '鼓楼区': (117.182, 34.317), '云龙区': (117.259, 34.233),
    '泉山区': (117.125, 34.215), '铜山区': (117.132, 34.168),
}
LANDMARKS = {
    '云龙湖': (117.136, 34.231), '大龙湖': (117.251, 34.200),
}
STATION_LABELS = {
    '路窝': (-7, -9), '客运北站': (9, 5), '彭城广场': (-8, -9), '徐州火车站': (8, -10),
    '徐州东站': (-9, -10), '淮塔': (-8, 5), '玉泉河': (-7, -10), '市行政中心': (7, -9),
    '振兴大道': (7, -9), '新城区东': (7, 8), '银山': (7, 11), '铜山中医院': (-7, -8),
}


class Panel:
    def __init__(self, name, x, y, width, height, bounds, pad=1.08):
        self.name, self.x, self.y, self.width, self.height = name, x, y, width, height
        west, south, east, north = bounds
        cx, cy = (west + east) / 2, (south + north) / 2
        span = max(east - west, (north - south) * width / height) * pad
        self.scale = width / span
        self.left, self.top = cx - span / 2, cy + height / self.scale / 2
        self.geom = box(self.left, self.top - height / self.scale, self.left + span, self.top)

    def project(self, x, y):
        return self.x + (x - self.left) * self.scale, self.y + (self.top - y) * self.scale


class Map:
    def __init__(self, city, panels):
        self.root = []
        self.origin = floor(city.bounds[0] / 1000) * 1000, ceil(city.bounds[3] / 1000) * 1000
        self.extent = shapely.union_all([panel.geom for panel in panels])

    def path_data(self, geom, kind, tolerance=0):
        if tolerance:
            geom = geom.simplify(tolerance, preserve_topology=kind == 'Polygon')

        def coordinate_path(coords, closed=False):
            result = []
            previous = None
            for a, b in coords:
                x, y = round(a - self.origin[0], 1), round(self.origin[1] - b, 1)
                if previous is None:
                    result.append(f'M{x:g},{y:g}')
                elif x == previous[0]:
                    if y != previous[1]:
                        result.append(f'V{y:g}')
                elif y == previous[1]:
                    result.append(f'H{x:g}')
                else:
                    result.append(f'L{x:g},{y:g}')
                previous = x, y
            return ''.join(result) + ('z' if closed else '')

        if kind == 'Polygon':
            return ''.join(coordinate_path(g.exterior.coords[:-1], True) +
                           ''.join(coordinate_path(r.coords[:-1], True) for r in g.interiors)
                           for g in pieces(geom, kind) if g.area > 1)
        return ''.join(coordinate_path(g.coords) for g in pieces(geom, kind) if g.length > .2)

    def attr_transform(self, panel):
        x, y = panel.project(*self.origin)
        return f'matrix({panel.scale:.11f} 0 0 {panel.scale:.11f} {x:.5f} {y:.5f})'

    def path(self, data, attrs=''):
        if data:
            self.root.append(f'<path d="{data}" {attrs}/>')

    def layer(self, name, geometries, kind, tolerance=0, minimum_area=0):
        self.root.append(f'<g id="{name}">')
        pending = []
        for geom in geometries:
            if geom.is_empty or not geom.intersects(self.extent):
                continue
            if kind == 'Polygon' and geom.area < minimum_area:
                continue
            if not self.extent.covers(geom):
                geom = geom.intersection(self.extent)
            data = self.path_data(geom, kind, tolerance)
            if data:
                pending.append(data)
            if len(pending) == 300:
                self.path(''.join(pending))
                pending.clear()
        self.path(''.join(pending))
        self.root.append('</g>')

    def use(self, panel, layer, attrs):
        self.root.append(f'<use href="#{layer}" xlink:href="#{layer}" transform="{self.attr_transform(panel)}" {attrs}/>')

    def stroke(self, panel, layer, color, pixels, extras=''):
        self.use(panel, layer, f'fill="none" stroke="{color}" stroke-width="{pixels / panel.scale:.3f}" {extras}')

    def text(self, x, y, value, size=16, color=INK, weight=400, extras=''):
        self.root.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" font-weight="{weight}" {extras}>{escape(value)}</text>')

    def rect(self, x, y, width, height, fill, extras=''):
        self.root.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="{fill}" {extras}/>')

    def line(self, x, y, end_x, end_y, color, width=1, extras=''):
        self.path(f'M{x:.2f},{y:.2f}L{end_x:.2f},{end_y:.2f}', f'fill="none" stroke="{color}" stroke-width="{width}" {extras}')

    def circle(self, x, y, radius, filled=True, caption=None, attrs=''):
        fill, outline = ('#243f4b', '#fff6ed') if filled else ('#fcfbf2', '#243f4b')
        title = f'<title>{escape(caption)}</title>' if caption else ''
        self.root.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" stroke="{outline}" stroke-width=".8" {attrs}>{title}</circle>')

    def scale(self, panel, km):
        right, top = panel.x + panel.width - 33, panel.y + 27
        self.text(right, top, '北', 13, weight=650, extras='text-anchor="middle"')
        self.path(f'M{right:.2f},{top + 7:.2f}l-6,22 6,-4 6,4z', f'fill="{INK}"')
        x, y = panel.x + 27, panel.y + panel.height - 27
        length = km * 1000 * panel.scale
        self.rect(x - 13, y - 25, length + 58, 39, '#fafbf6', 'rx="4" opacity=".94"')
        self.line(x, y, x + length, y, INK, 1.2)
        for fraction, label in [(0, '0'), (.5, f'{km / 2:g}'), (1, f'{km} 公里')]:
            offset = x + length * fraction
            self.line(offset, y - 4, offset, y + 4, INK, 1.2)
            self.text(offset, y - 8, label, 12, weight=500, extras='text-anchor="middle"')


def draw(output):
    stamp, boundaries, _, _, polygons, _, municipality, basemap, _, line_centers = load_extract()
    city = municipality[1]
    stations, _, _, _, _, _, counts, _, _ = load_routes()
    with (ROOT / 'coverage-xuzhou.pkl').open('rb') as stream:
        tiles = pickle.load(stream)
    station_bounds = shapely.MultiPoint([*line_centers.values(), *(s['xy'] for s in stations.values())]).buffer(1700).bounds
    main = Panel('whole', 46, 190, 750, 650, city.bounds)
    detail = Panel('detail', 829, 190, 935, 1008, station_bounds, pad=1.01)
    grid = Map(city, (main, detail))
    root = grid.root
    root.extend([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">徐州市地铁步行一公里覆盖图</title>',
        '<desc id="desc">徐州全市行政区总览与运营地铁线网覆盖区放大图。珊瑚红表示由已标注站口出发的步行一公里范围，浅橙表示以车站附近推定接驳点补算的范围。车站圆点可悬停查站名。</desc>',
        f'<metadata>OpenStreetMap contributors (ODbL), Geofabrik Jiangsu snapshot {escape(stamp)}. WGS 84 / UTM 50N. Network budget: 1000 m. Surface cell: 8 m.</metadata>',
        '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC","PingFang SC","Source Han Sans SC",sans-serif} .label{paint-order:stroke fill;stroke:#fcfbf2;stroke-width:3.4;stroke-linejoin:round} a text{text-decoration:underline}</style>',
        '<defs>',
    ])
    for panel in (main, detail):
        root.append(f'<clipPath id="clip-{panel.name}"><rect x="{panel.x}" y="{panel.y}" width="{panel.width}" height="{panel.height}" rx="4"/></clipPath>')
    grid.layer('municipality', [city], 'Polygon', 15)
    grid.layer('parks', (g for _, _, g in polygons['green']), 'Polygon', 11, 12000)
    grid.layer('water', (g for _, _, g in polygons['water']), 'Polygon', 8, 1700)
    grid.layer('waterline', basemap['waterline'], 'LineString', 9)
    for name, (_, _, _, tolerance) in ROAD_STYLES.items():
        grid.layer(name, basemap[name], 'LineString', tolerance)
    grid.layer('walk-area', (area for _, area, *_ in tiles), 'Polygon', 1.2)
    grid.layer('walk-roads', (roads for _, _, roads, *_ in tiles), 'LineString')
    grid.layer('known-area', (area for _, _, _, area, _ in tiles), 'Polygon', 1.2)
    grid.layer('known-roads', (roads for _, _, _, _, roads in tiles), 'LineString')
    boundary = shapely.union_all([geom.boundary for _, geom in boundaries.values()])
    grid.layer('county-border', [boundary], 'LineString', 9)
    grid.layer('municipal-border', [city.boundary], 'LineString', 9)
    root.append('</defs>')

    grid.rect(0, 0, WIDTH, HEIGHT, PAPER)
    grid.text(46, 42, '徐州市', 18, '#456370', 600)
    grid.text(43, 105, '地铁步行一公里覆盖图', 56, INK, 700)
    grid.text(47, 140, '按运营车站出入口与估算接驳点的步行路网距离计算', 18, MUTED)
    local_date = datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).date().isoformat()
    grid.text(1764, 45, f'路网快照  {local_date}', 16, '#546c72', 500, 'text-anchor="end"')
    grid.text(1764, 82, f'4 条运营线路  /  {len(stations)} 座车站', 21, INK, 700, 'text-anchor="end"')
    grid.line(46, 154, 1764, 154, '#cbd7d6')
    grid.text(main.x, 179, '全市总览', 19, weight=700)
    grid.text(detail.x, 179, '运营线网覆盖区放大', 19, weight=700)

    for panel in (main, detail):
        root.append(f'<g clip-path="url(#clip-{panel.name})">')
        grid.rect(panel.x, panel.y, panel.width, panel.height, '#eeefe9')
        grid.use(panel, 'municipality', f'fill="{LAND}" fill-rule="evenodd"')
        if panel is detail:
            grid.use(panel, 'parks', 'fill="#dce8d5" fill-rule="evenodd" opacity=".72"')
        grid.stroke(panel, 'waterline', '#bed7df', .65 if panel is main else .84)
        grid.use(panel, 'water', 'fill="#d4e7ee" fill-rule="evenodd"')
        for layer, (color, overview, inset, _) in ROAD_STYLES.items():
            width = overview if panel is main else inset
            if width:
                extra = f'stroke-dasharray="{2.6 / panel.scale:.3f} {2.9 / panel.scale:.3f}"' if layer == 'rail' else 'stroke-linecap="round"'
                grid.stroke(panel, layer, color, width, extra)
        grid.use(panel, 'walk-area', f'fill="{ESTIMATE}" fill-rule="evenodd"')
        grid.use(panel, 'known-area', f'fill="{CORAL}" fill-rule="evenodd"')
        grid.stroke(panel, 'walk-roads', ESTIMATE_ROADS, .25 if panel is main else .50, 'opacity=".82"')
        grid.stroke(panel, 'known-roads', RED, .28 if panel is main else .55, 'opacity=".91"')
        grid.stroke(panel, 'county-border', TEAL, 1.02 if panel is main else 1.35, 'opacity=".82"')
        grid.stroke(panel, 'municipal-border', TEAL, 1.7)
        for name, station in stations.items():
            x, y = panel.project(*station['xy'])
            connected = bool(station['matched'])
            qualification = '' if connected else ' · 出入口未接入路网'
            if connected and counts[name] < 20:
                qualification = ' · 周边步行路网较稀疏'
            if connected and any(origin != 'OSM' for _, _, origin, _ in station['matched']):
                qualification = ' · 含估算接驳'
            if name == '徐州东站':
                qualification += ' · 1、6号线站外换乘'
                if panel is detail and line_centers[1, name] != line_centers[6, name]:
                    qx, qy = panel.project(*line_centers[6, name])
                    grid.circle(qx, qy, 2.7, connected, f'徐州东站 · 6号线站区{qualification}')
            caption = f"{name} · {' / '.join(station['lines'])}{qualification}"
            grid.circle(x, y, 1.59 if panel is main else 2.7, connected, caption, f'data-station="{escape(name)}"')
            if panel is detail and name in STATION_LABELS:
                dx, dy = STATION_LABELS[name]
                alignment = 'start' if dx > 0 else 'end'
                grid.text(x + dx, y + dy, name, 13, weight=650, extras=f'text-anchor="{alignment}" class="label"')
        if panel is main:
            x1, y1, x2, y2 = detail.geom.bounds
            x, y = panel.project(x1, y2)
            grid.rect(x, y, (x2 - x1) * panel.scale, (y2 - y1) * panel.scale, 'none', 'stroke="#537178" stroke-width="1.05" stroke-dasharray="4 4"')
        for name, reference in (COUNTY_LABELS if panel is main else DETAIL_LABELS).items():
            geom = boundaries[name][1]
            location = Point(projection.transform(*reference))
            if not geom.covers(location):
                visible = geom.intersection(panel.geom)
                if visible.is_empty:
                    continue
                location = max(pieces(visible, 'Polygon'), key=lambda p: p.area).representative_point()
            x, y = panel.project(location.x, location.y)
            if panel is main and name in {'鼓楼区', '泉山区', '云龙区'}:
                dx, dy = {'鼓楼区': (56, -30), '泉山区': (-43, 4), '云龙区': (53, 24)}[name]
                grid.line(x, y, x + dx * .8, y + dy * .78, '#68838b', .8)
                x, y = x + dx, y + dy
            grid.text(x, y, name, 17 if panel is detail else 16, weight=700, extras=f'text-anchor="middle" class="label" data-county="{escape(name)}"')
        if panel is detail:
            for name, location in LANDMARKS.items():
                x, y = panel.project(*projection.transform(*location))
                grid.text(x, y, name, 14, '#5d8694', 600, 'text-anchor="middle" class="label"')
        grid.scale(panel, 20 if panel is main else 4)
        root.append('</g>')
        grid.rect(panel.x, panel.y, panel.width, panel.height, 'none', 'rx="4" stroke="#9fb6bc" stroke-width="1"')

    x = main.x
    grid.text(x, 875, '图例', 20, weight=700)
    grid.rect(x, 890, 22, 15, CORAL, 'rx="2"')
    grid.text(x + 34, 903, '步行 ≤ 1 公里 · 已标注站口', 16, weight=650)
    grid.line(x, 930, x + 22, 930, RED, 2)
    grid.text(x + 34, 935, '依据已标注站口的可达路段', 16)
    grid.circle(x + 10, 963, 4)
    grid.text(x + 34, 969, '运营车站（悬停看站名与所属线路）', 16)
    grid.rect(x + 375, 890, 22, 15, ESTIMATE, 'rx="2"')
    grid.text(x + 409, 903, '步行 ≤ 1 公里 · 估算接驳点', 16, weight=650)
    grid.line(x + 375, 930, x + 397, 930, TEAL, 1.8)
    grid.text(x + 409, 935, '徐州市界 / 区县界', 16)
    if any(not station['matched'] for station in stations.values()):
        grid.circle(x + 385, 963, 4, filled=False)
        grid.text(x + 409, 969, '出入口未接入路网', 16)
    else:
        grid.line(x + 375, 963, x + 397, 963, '#537178', 1, 'stroke-dasharray="4 4"')
        grid.text(x + 409, 969, '右图放大范围', 16)
    grid.line(x, 989, main.x + main.width, 989, '#cbd7d6')
    estimated_count = sum(any(source == '站位估算' for _, _, source, _ in s['matched']) for s in stations.values())
    for i, item in enumerate([
        '沿可步行道路、人行道、桥和通道计算，步行可跨越区县界。',
        f'{estimated_count} 座车站采用站位附近的路网接驳点补算，地表范围按 8 米网格估算。',
        '徐州东站按 1、6 号线站区分别估算接驳点，站点统计合并计一座。',
        '站口、步道或门禁的缺绘会影响局部范围。',
    ]):
        grid.text(x, 1012 + 23 * i, item, 15, MUTED)
    grid.line(x, 1100, main.x + main.width, 1100, '#cbd7d6')
    for i, (url, label) in enumerate([
        ('https://www.openstreetmap.org/copyright', '© OpenStreetMap contributors · ODbL'),
        ('https://download.geofabrik.de/asia/china/jiangsu.html', 'Geofabrik 江苏路网快照'),
        ('https://www.xzdtjt.com/1/52/station', '徐州地铁 · 运营车站与出入口指南'),
        ('https://maps.gaode.com/ssr/subway/xuzhou-3203', '高德地图 · 线网与换乘信息'),
    ]):
        root.append(f'<a href="{escape(url)}" xlink:href="{escape(url)}">')
        grid.text(x + (i % 2) * 375, 1123 + (i // 2) * 23, label, 13, '#486972')
        root.append('</a>')
    root.append('</svg>')
    svg = '\n'.join(root)
    if len(stations) != 70 or set(stations) != STATION_NAMES or svg.count('data-station=') != 140:
        raise ValueError('Station count does not match the operating roster')
    output.write_text(svg, encoding='utf-8')
    print(f'{output.name} · {output.stat().st_size / 1e6:.2f} MB', flush=True)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Render the Xuzhou coverage map as SVG.')
    parser.add_argument('output', type=Path)
    draw(parser.parse_args().output)
