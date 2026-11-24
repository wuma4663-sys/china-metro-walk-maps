import html
import math
from datetime import datetime,timedelta,timezone

from common import *
from coverage import pieces
from route_wuxi import load_routes

stamp,districts,points,ways,polys,relations,municipal,basemap = read_model()
city,*_ = load_routes()
with (folder/'augmented.pkl').open('rb') as f:
    stations,*_=pickle.load(f)
with (folder/'coverage-verified.pkl').open('rb') as f:
    tiles = pickle.load(f)
with (folder/'coverage-estimated.pkl').open('rb') as f:
    estimated_tiles = pickle.load(f)

WIDTH,HEIGHT = 1910,1370
ink,muted,teal = '#1b3844','#536970','#244c5b'
water ='#dfedf2'
coral, red = '#fa806b','#bf3e31'
peach, peach_road = '#fac2a6','#b87553'
paper, map_land, city_land = '#faf9f5','#edece4','#fcfbf2'
west,south,east,north=city.bounds
U0,V0=math.floor(west/1000)*1000,math.ceil(north/1000)*1000
root=[]


def esc(v):
    return html.escape(str(v),quote=True)


class Panel:
    def __init__(self,name,x,y,w,h,center,span):
        self.name,self.x,self.y,self.w,self.h = name,x,y,w,h
        self.scale = w/span
        cx,cy = center
        self.left,self.top = cx-span/2,cy+h/self.scale/2
        self.box = box(self.left,self.top-h/self.scale,self.left+span,self.top)
    def add(self,x,y):
        return (self.x+(x-self.left)*self.scale,self.y+(self.top-y)*self.scale)
    def place(self,h,draw_attrs=''):
        a=self.scale
        x,y=self.add(U0,V0)
        root.append(f'<use href="#{h}" xlink:href="#{h}" transform="matrix({a:.11f} 0 0 {a:.11f} {x:.5f} {y:.5f})" {draw_attrs}/>')


span=max(east-west,(north-south)*1080/1114)*1.072
main=Panel('city',46,190,1080,1114,((west+east)/2,(south+north)/2),span)
detail=Panel('center',1156,190,708,528,projection.transform(120.333,31.558),40800)
jiangyin=Panel('jiangyin',1156,765,708,257,projection.transform(120.267,31.882),30200)
panels = (main, detail, jiangyin)
main_geom=main.box


def gpath(geom,kind,generalize=0):
    if geom.is_empty:
        return ''
    if generalize:
        geom=geom.simplify(generalize,preserve_topology=(kind=='Polygon'))
    def design(coords,close=False):
        result=[]
        prev=None
        for ax,ay in coords:
            x,y=round(ax-U0,1),round(V0-ay,1)
            if prev is None:
                result.append(f'M{x:g},{y:g}')
            elif x==prev[0]:
                if y!=prev[1]:
                    result.append(f'V{y:g}')
            elif y==prev[1]:
                result.append(f'H{x:g}')
            else:
                result.append(f'L{x:g},{y:g}')
            prev=x,y
        if close:
            result.append('z')
        return ''.join(result)
    if kind=='Polygon':
        return ''.join(design(p.exterior.coords[:-1],True)+''.join(design(r.coords[:-1],True) for r in p.interiors)
                       for p in pieces(geom,'Polygon') if p.area>1)
    return ''.join(design(p.coords) for p in pieces(geom,'LineString') if p.length>.2)


def path(d,attrs=''):
    if d:
        root.append(f'<path d="{d}" {attrs}/>')


def text(x,y,s,size=16,color=ink,weight=400,extras=''):
    root.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" font-weight="{weight}" {extras}>{esc(s)}</text>')


def rect(x,y,w,h,fill,extras=''):
    root.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{fill}" {extras}/>')


def line(x,y,ex,ey,color,width=1,extras=''):
    path(f'M{x:.2f},{y:.2f}L{ex:.2f},{ey:.2f}',f'fill="none" stroke="{color}" stroke-width="{width}" {extras}')


def use_lines(panel,ref,color,px,extras=''):
    panel.place(ref,f'fill="none" stroke="{color}" stroke-width="{px/panel.scale:.3f}" {extras}')


def add_def(name,geo,kind,tol,threshold=0):
    root.append(f'<g id="{name}">')
    parts = []
    for g in geo:
        if g.is_empty or not g.intersects(main_geom):
            continue
        if kind=='Polygon' and g.area<threshold:
            continue
        if not main_geom.covers(g):
            g=main_geom.intersection(g)
        d=gpath(g,kind,tol)
        if not d:
            continue
        parts.append(d)
        if len(parts)>350:
            path(''.join(parts))
            parts.clear()
    if parts:
        path(''.join(parts))
    root.append('</g>')


rendered_districts = {n:(i,g.intersection(main_geom)) for n,(i,g) in districts.items() if n in DISTRICTS}
wuxi_land=city.intersection(main_geom)
basemap_land=main_geom
display_borders=shapely.union_all([g.boundary.intersection(main_geom) for n,(_,g) in districts.items() if n in DISTRICTS])
city_border = city.boundary.intersection(main_geom)
major_waters=shapely.union_all([g.intersection(main_geom) for _,_,g in polys['water'] if g.area>2e6 and g.intersects(main_geom)])
dry_limits = main_geom.difference(major_waters).buffer(45)

root.append('<?xml version="1.0" encoding="UTF-8"?>')
root.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">')
root.append('<title id="title">无锡市地铁步行一公里覆盖图</title>')
root.append('<desc id="desc">无锡全市五个市辖区和两个县级市的地铁步行一公里覆盖图。珊瑚红色块是按最短步行路网距离和八米地表网格计算的估计范围。深红线表示可达步行路段。浅红区为根据车站周边公用路网估算接驳所得到的覆盖。右侧是中心城区和江阴 S1 线放大图。</desc>')
root.append(f'<metadata>Roads, waterways and boundaries: OpenStreetMap contributors, ODbL, https://www.openstreetmap.org/copyright. Geofabrik Jiangsu snapshot {esc(stamp)}. WGS84/UTM 51N. Maximum walking network distance 1000 m. Surface estimate grid 8 m.</metadata>')
root.append('<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC","PingFang SC","Source Han Sans SC",sans-serif} .label {paint-order:stroke fill;stroke:#fcfcf7;stroke-width:3.4;stroke-linejoin:round} a text{text-decoration:underline}</style>')
root.append('<defs>')
for p in panels:
    root.append(f'<clipPath id="{p.name}-clip"><rect x="{p.x}" y="{p.y}" width="{p.w}" height="{p.h}" rx="4"/></clipPath>')
mx,my=main.add(U0,V0)
scale=main.scale
outline = gpath(wuxi_land,'Polygon',3)
root.append(f'<clipPath id="overview-city-land"><path d="{outline}" clip-rule="evenodd" transform="matrix({scale:.11f} 0 0 {scale:.11f} {mx:.5f} {my:.5f})"/></clipPath>')
add_def('base-land',[basemap_land],'Polygon',21)
add_def('wuxi-land',[wuxi_land],'Polygon',16)
park_shapes = [g.intersection(basemap_land) for _,_,g in polys['green'] if g.area>=42000 and g.intersects(basemap_land)]
add_def('parks',park_shapes,'Polygon',12,42000)
add_def('water-area',[g for _,_,g in polys['water']],'Polygon',9,1900)
for name,tol in {'street':5,'minor':7,'main':10,'rail':11,'waterline':12}.items():
    add_def(name,basemap[name],'LineString',tol)
root.append('<g id="walk-area" fill-rule="evenodd">')
for _,coverage,_ in tiles:
    path(gpath(coverage,'Polygon',1.2))
root.append('</g><g id="walk-roads">')
for tile,coverage,roads in tiles:
    path(gpath(roads,'LineString'))
root.append('</g><g id="estimated-area" fill-rule="evenodd">')
for _,coverage,_ in estimated_tiles:
    path(gpath(coverage,'Polygon',1.2))
root.append('</g><g id="estimated-roads">')
for _,_,roads in estimated_tiles:
    path(gpath(roads,'LineString'))
root.append('</g><g id="district-areas">')
for name,(oid,g) in sorted(rendered_districts.items()):
    path(gpath(g,'Polygon',10),f'id="district-{oid}" data-name="{esc(name)}"')
root.append('</g>')
add_def('district-dry-borders',[display_borders.intersection(dry_limits)],'LineString',7)
add_def('district-wet-borders',[display_borders.difference(dry_limits)],'LineString',12)
add_def('city-dry-border',[city_border.intersection(dry_limits)],'LineString',9)
add_def('city-wet-border',[city_border.difference(dry_limits)],'LineString',15)
root.append('</defs>')

rect(0,0,WIDTH,HEIGHT,paper)
text(46,42,'无锡市',18,'#456370',600)
text(43,105,'地铁步行一公里覆盖图',56,ink,700)
text(47,140,'以运营车站为起点，沿步行路网计算最短距离',18,muted)
local_date=datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).date().isoformat()
text(1864,45,f'路网快照  {local_date}',16,'#546c72',500,'text-anchor="end"')
text(1864,82,f'5 条运营线路 · {len(stations)} 座车站',23,ink,700,'text-anchor="end"')
text(1864,112,'运营线网截至 2026-11-24',15,muted,500,'text-anchor="end"')
line(46,154,1864,154,'#cbd7d6')
text(46,179,'全市总览',19,ink,700)
text(1156,179,'中心城区放大',19,ink,700)
text(1156,754,'江阴城区 · S1 线',19,ink,700)


all_labels = {
    '梁溪区':(120.348,31.617), '锡山区':(120.485,31.664), '惠山区':(120.153,31.664),
    '滨湖区':(120.170,31.493), '新吴区':(120.402,31.451),
    '江阴市':(120.213,31.826), '宜兴市':(119.824,31.352),
}
center_labels = {
    '梁溪区':(120.331,31.634), '锡山区':(120.471,31.626), '惠山区':(120.215,31.639),
    '滨湖区':(120.244,31.481), '新吴区':(120.414,31.478),
}
panel_labels={'city':all_labels,'center':center_labels,'jiangyin':{}}
shore_labels={
    'city':[('太湖',120.082,31.371),('长江',120.340,31.960),('滆湖',119.853,31.514)],
    'center':[('太湖',120.173,31.498),('蠡湖',120.241,31.525)],
    'jiangyin':[('长江',120.207,31.922)],
}
named_stations = {
    'city': {},
    'center': {'堰桥':(8,-6),'马镇':(8,-5),'苏庙':(-7,-7),'梅园开原寺':(-7,15),
               '无锡火车站':(9,-13),'三阳广场':(8,21),'无锡东站':(9,-8),
               '硕放机场':(9,-5),'南方泉':(9,5),'博览中心':(8,17)},
    'jiangyin': {'南闸':(9,3),'江阴高铁站':(9,4),'江阴中医院':(-9,5),'南门':(9,4),
                 '中山公园':(9,4),'江阴外滩':(9,8)},
}


def anchor(name,panel):
    reference=Point(projection.transform(*panel_labels[panel.name][name]))
    geom=districts[name][1]
    if geom.covers(reference) and panel.box.covers(reference):
        return reference.coords[0]
    visible=geom.intersection(panel.box).intersection(dry_limits)
    return max(pieces(visible,'Polygon'),key=lambda p:p.area).representative_point().coords[0]


def annotate_measure(p,span):
    right,top=p.x+p.w-38,p.y+29
    text(right,top,'北',13,ink,600,'text-anchor="middle"')
    path(f'M{right:.2f},{top+7:.2f}l-6,22 6,-4 6,4z',f'fill="{ink}"')
    x,y=p.x+27,p.y+p.h-28
    end=span*1000*p.scale
    rect(x-14,y-24,end+59,40,'#fafbf6','rx="3" opacity=".9"')
    line(x,y,x+end,y,ink,1.2)
    for i in range(3):
        a=x+i*end/2
        line(a,y-4,a,y+4,ink,1.2)
        label='0' if i==0 else f'{span/2:g}' if i==1 else f'{span} 公里'
        text(a,y-8,label,12,ink,500,'text-anchor="middle"')


for p in panels:
    root.append(f'<g clip-path="url(#{p.name}-clip)">')
    rect(p.x,p.y,p.w,p.h,water)
    p.place('base-land',f'fill="{map_land}" fill-rule="evenodd"')
    p.place('wuxi-land',f'fill="{city_land}" fill-rule="evenodd"')
    if p==main:
        root.append('<g clip-path="url(#overview-city-land)">')
    p.place('parks','fill="#dce8d5" fill-rule="evenodd" opacity=".66"')
    use_lines(p,'waterline','#c8dce2',.62)
    if p==main:
        root.append('</g>')
    p.place('water-area','fill="#d4e7ee" fill-rule="evenodd"')
    if p==main:
        root.append('<g clip-path="url(#overview-city-land)">')
    if p!=main:
        use_lines(p,'street','#d4d8d0',.5,extras='stroke-linecap="round"')
    use_lines(p,'minor','#d6d9d1',.44 if p==main else .65)
    use_lines(p,'main','#bec9c7',.68 if p==main else .95,extras='stroke-linecap="round"')
    use_lines(p,'rail','#a2b4bc',.60 if p==main else .73,extras=f'stroke-dasharray="{2.5/p.scale:.3f} {2.8/p.scale:.3f}"')
    if p==main:
        root.append('</g>')
    p.place('estimated-area',f'fill="{peach}" fill-rule="evenodd"')
    use_lines(p,'estimated-roads',peach_road,.28 if p==main else .52,extras='stroke-linecap="butt" opacity=".85"')
    p.place('walk-area',f'fill="{coral}" fill-rule="evenodd"')
    use_lines(p,'walk-roads',red,.28 if p==main else .57,extras='stroke-linecap="butt" opacity=".91"')
    use_lines(p,'district-dry-borders',teal,1.11 if p==main else 1.38,extras='stroke-linejoin="round"')
    use_lines(p,'district-wet-borders','#7198a4',.93,extras=f'stroke-dasharray="{3.5/p.scale:.3f} {3.3/p.scale:.3f}"')
    use_lines(p,'city-dry-border',teal,1.82 if p==main else 1.65,extras='stroke-linejoin="round"')
    use_lines(p,'city-wet-border','#73949e',1.25,extras=f'stroke-dasharray="{6/p.scale:.3f} {3.5/p.scale:.3f}"')
    if p==main:
        for inset in (detail, jiangyin):
            ll,bot,rr,top=inset.box.bounds
            x,y=p.add(ll,top)
            w,h=(rr-ll)*p.scale,(top-bot)*p.scale
            rect(x,y,w,h,'none','stroke="#537178" stroke-width="1.05" stroke-dasharray="4 4"')
    for name,lon,lat in shore_labels[p.name]:
        xy=projection.transform(lon,lat)
        if p.box.covers(Point(xy)):
            ax,ay=p.add(*xy)
            text(ax,ay,name,16,'#68838b',500,'text-anchor="middle" class="label" letter-spacing="1.3"')
    for name,s in stations.items():
        pos=Point(s['xy'])
        if not p.box.covers(pos) or (not city.covers(pos) and not s['matched']):
            continue
        ax,ay=p.add(*s['xy'])
        r=1.8 if p==main else 2.35
        display_name=f"{name} · {' / '.join(s['lines'])}"
        if s.get('estimated'):
            display_name+=' · 接驳估算'
        if not s['matched']:
            display_name+=' · 出入口未接入路网'
        style='fill="#243f4b" stroke="#fff6ed"' if s['matched'] else 'fill="#fbfaf2" stroke="#243f4b"'
        if s.get('estimated'):
            style='fill="#fff3eb" stroke="#9b4e30"'
        root.append(f'<circle cx="{ax:.2f}" cy="{ay:.2f}" r="{r}" {style} stroke-width=".8" data-station="{esc(name)}"><title>{esc(display_name)}</title></circle>')
        if name in named_stations[p.name]:
            dx,dy=named_stations[p.name][name]
            align='end' if dx<0 else 'start'
            text(ax+dx,ay+dy,name,12,ink,650,f'text-anchor="{align}" class="label"')
    for name in panel_labels[p.name]:
        x,y=p.add(*anchor(name,p))
        text(x,y,name,21 if p==main else 18,ink,700,
             f'text-anchor="middle" class="label" data-district="{esc(name)}"')
    annotate_measure(p,10 if p==main else 4)
    root.append('</g>')
    rect(p.x,p.y,p.w,p.h,'none','rx="4" stroke="#9fb6bc" stroke-width="1"')

x=1156
text(x,1060,'图例',22,ink,700)
rect(x,1078,22,15,coral,'rx="2"')
text(x+33,1091,'有站口坐标的步行覆盖',16,ink,650)
line(x,1112,x+22,1112,red,2)
text(x+33,1117,'步行 ≤ 1 公里的路段',15)
rect(x+377,1078,22,15,peach,'rx="2"')
text(x+410,1091,'按站口接驳估算的步行范围',15)
line(x+377,1112,x+399,1112,teal,1.65)
text(x+410,1117,'市界 / 区界（水上为虚线）',15)
root.append(f'<circle cx="{x+10}" cy="1137" r="3.8" fill="#243f4b" stroke="#fff6ed" stroke-width=".8"/>')
text(x+33,1142,'运营车站（悬停查看站名和线路）',15)
root.append(f'<circle cx="{x+388}" cy="1137" r="3.8" fill="#fff3eb" stroke="#9b4e30" stroke-width="1"/>')
text(x+410,1142,'站口接驳估算',15)
if any(not s['matched'] for s in stations.values()):
    text(x+540,1142,'；空心灰点为未接入',14,muted)
line(x,1162,1864,1162,'#cbd7d6')
text(x,1189,'读图说明',19,ink,700)
for i,label in enumerate([
    '沿道路、人行道、桥和通道计算，步行可跨区界。',
    f"色块按 8 米网格估算；{sum(s.get('estimated',False) for s in stations.values())} 座站采用邻近公共道路估算接驳。",
    '覆盖 1–4 号线和 S1 线，含江阴；4 号线二期尚待开通。',
]):
    text(x,1217+i*24,label,15,muted)
links = [
    ('https://www.openstreetmap.org/copyright','© OpenStreetMap contributors · ODbL'),
    ('https://download.geofabrik.de/asia/china/jiangsu.html','Geofabrik 江苏路网快照'),
    ('https://maps.gaode.com/ssr/subway/wuxi-3202','高德地图运营站点'),
]
for xl,(url,label) in zip((46,384,673),links):
    root.append(f'<a href="{esc(url)}" xlink:href="{esc(url)}">')
    text(xl,1339,label,13,'#486972')
    root.append('</a>')
root.append('</svg>')
svg='\n'.join(root)
(folder/'wuxi-walk.svg').write_text(svg,encoding='utf-8')
print('Size',round(len(svg.encode('utf-8'))/1e6,2),'MB',flush=True)
