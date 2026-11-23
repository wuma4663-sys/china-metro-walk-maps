import html
import math
from datetime import datetime,timedelta,timezone

from common import *
from coverage import pieces
from route_nanjing import load_routes

stamp,districts,points,ways,polys,relations,municipal,basemap = read_model()
city,stations,_,_,_,_,_,_,contribution = load_routes()
with (folder/'coverage.pkl').open('rb') as f:
    tiles = pickle.load(f)

WIDTH,HEIGHT = 1810,1260
ink,muted,teal = '#1b3844','#536970','#244c5b'
water ='#dfedf2'
coral, red = '#fa806b','#bf3e31'
paper, map_land, city_land = '#faf9f5','#eef0e8','#fcfbf2'
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


cross_areas = external_areas(city)
cross_stations = external_stops()
scope = study_area(city)
span=max(east-west,(north-south)*960/1020)*1.065
main=Panel('city',46,190,960,1020,((west+east)/2,(south+north)/2),span)
detail=Panel('center',1040,190,724,497,projection.transform(118.797,32.052),35400)
cross_panels={}
for i,(key,area) in enumerate(cross_areas.items()):
    left,bottom,right,top=area.bounds
    w,h=352,250
    cross_panels[key]=Panel(key,1040+372*i,727,w,h,((left+right)/2,(bottom+top)/2),
                            max((right-left)*1.15,(top-bottom)*w/h*1.10))
panels = (main,detail,*cross_panels.values())
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
nanjing_land=city.intersection(main_geom)
basemap_land=scope.intersection(main_geom)
display_borders=shapely.union_all([g.boundary.intersection(main_geom) for n,(_,g) in districts.items() if n in DISTRICTS])
city_border = city.boundary.intersection(main_geom)
major_waters=shapely.union_all([g.intersection(main_geom) for _,_,g in polys['water'] if g.area>2e6 and g.intersects(main_geom)])
dry_limits = main_geom.difference(major_waters).buffer(45)

root.append('<?xml version="1.0" encoding="UTF-8"?>')
root.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">')
root.append('<title id="title">南京市地铁步行一公里覆盖图</title>')
root.append('<desc id="desc">南京全市十一个区的地铁步行一公里覆盖图。珊瑚红色块按最短步行路网距离和八米地表网格估算。深红线表示可达步行路段。右侧放大中心城区及宁马线、宁句线的跨市站点周边。</desc>')
root.append(f'<metadata>Roads, waterways and boundaries: OpenStreetMap contributors, ODbL, https://www.openstreetmap.org/copyright. Geofabrik Jiangsu and Anhui extracts, Jiangsu snapshot {esc(stamp)}. WGS84/UTM 50N. Maximum walking network distance 1000 m. Surface estimate grid 8 m.</metadata>')
root.append('<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC","PingFang SC","Source Han Sans SC",sans-serif} .label {paint-order:stroke fill;stroke:#fcfcf7;stroke-width:3.4;stroke-linejoin:round} a text{text-decoration:underline}</style>')
root.append('<defs>')
for p in panels:
    root.append(f'<clipPath id="{p.name}-clip"><rect x="{p.x}" y="{p.y}" width="{p.w}" height="{p.h}" rx="4"/></clipPath>')
    x,y = p.add(U0,V0)
    visible = cross_areas.get(p.name,scope).intersection(p.box)
    root.append(f'<clipPath id="{p.name}-scope"><path d="{gpath(visible,"Polygon")}" clip-rule="evenodd" transform="matrix({p.scale:.11f} 0 0 {p.scale:.11f} {x:.5f} {y:.5f})"/></clipPath>')
add_def('base-land',[basemap_land],'Polygon',21)
add_def('nanjing-land',[nanjing_land],'Polygon',16)
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
text(46,42,'南京市',18,'#456370',600)
text(43,105,'地铁步行一公里覆盖图',56,ink,700)
text(47,140,'按步行路网到最近运营车站出入口的最短距离计算',18,muted)
local_date=datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).date().isoformat()
text(1764,45,f'路网快照  {local_date}',16,'#546c72',500,'text-anchor="end"')
text(1764,82,'11 个市辖区  /  15 条运营线路',21,ink,700,'text-anchor="end"')
line(46,154,1764,154,'#cbd7d6')
text(46,179,'全市总览',19,ink,700)
text(1040,179,'中心城区放大',19,ink,700)
text(1040,717,'S2 宁马线 · 马鞍山市',17,ink,700)
text(1412,717,'S6 宁句线 · 镇江市句容市',17,ink,700)


all_labels = {
    '浦口区':(118.521,32.072),'六合区':(118.879,32.394),'栖霞区':(119.031,32.165),
    '鼓楼区':(118.766,32.105),'玄武区':(118.860,32.083),'秦淮区':(118.826,32.019),
    '建邺区':(118.693,32.000),'雨花台区':(118.676,31.938),'江宁区':(118.762,31.799),
    '溧水区':(119.027,31.550),'高淳区':(119.005,31.328),
}
center_labels = {name:all_labels[name] for name in (
    '浦口区','栖霞区','鼓楼区','玄武区','秦淮区','建邺区','雨花台区','江宁区')}
center_labels.update({'浦口区':(118.670,32.091),'栖霞区':(118.937,32.118),'江宁区':(118.883,31.977)})
panel_labels={'city':list(all_labels),'center':list(center_labels)}
cross_labels=[
    ('马鞍山市 · S2',118.415,31.685),('镇江市句容市 · S6',119.280,31.963),
]


def anchor(name,panel):
    label=center_labels[name] if panel==detail else all_labels[name]
    reference=Point(projection.transform(*label))
    geom=districts[name][1]
    if geom.covers(reference) and panel.box.covers(reference):
        return tuple(reference.coords)[0]
    in_panel=geom.intersection(panel.box)
    dry = in_panel.intersection(dry_limits)
    polygons = list(pieces(dry,'Polygon')) or list(pieces(in_panel,'Polygon'))
    if not polygons:
        return None
    print('Adjusted district label',name,panel.name,flush=True)
    return tuple(max(polygons,key=lambda p:p.area).representative_point().coords)[0]


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
    rect(p.x,p.y,p.w,p.h,'#fffefa')
    root.append(f'<g clip-path="url(#{p.name}-scope)">')
    p.place('base-land',f'fill="{map_land}" fill-rule="evenodd"')
    p.place('nanjing-land',f'fill="{city_land}" fill-rule="evenodd"')
    p.place('parks','fill="#dce8d5" fill-rule="evenodd" opacity=".66"')
    use_lines(p,'waterline','#c8dce2',.62)
    p.place('water-area','fill="#d4e7ee" fill-rule="evenodd"')
    if p!=main:
        use_lines(p,'street','#d4d8d0',.5,extras='stroke-linecap="round"')
    use_lines(p,'minor','#d6d9d1',.44 if p==main else .65)
    use_lines(p,'main','#bec9c7',.68 if p==main else .95,extras='stroke-linecap="round"')
    use_lines(p,'rail','#a2b4bc',.60 if p==main else .73,extras=f'stroke-dasharray="{2.5/p.scale:.3f} {2.8/p.scale:.3f}"')
    p.place('walk-area',f'fill="{coral}" fill-rule="evenodd"')
    use_lines(p,'walk-roads',red,.28 if p==main else .57,extras='stroke-linecap="butt" opacity=".91"')
    use_lines(p,'district-dry-borders',teal,1.11 if p==main else 1.38,extras='stroke-linejoin="round"')
    use_lines(p,'district-wet-borders','#7198a4',.93,extras=f'stroke-dasharray="{3.5/p.scale:.3f} {3.3/p.scale:.3f}"')
    use_lines(p,'city-dry-border',teal,1.82 if p==main else 1.65,extras='stroke-linejoin="round"')
    use_lines(p,'city-wet-border','#73949e',1.25,extras=f'stroke-dasharray="{6/p.scale:.3f} {3.5/p.scale:.3f}"')
    root.append('</g>')
    if p==main:
        ll,bot,rr,top=detail.box.bounds
        x,y=p.add(ll,top)
        w,h=(rr-ll)*p.scale,(top-bot)*p.scale
        rect(x,y,w,h,'none','stroke="#537178" stroke-width="1.05" stroke-dasharray="4 4"')
        for name,lon,lat in cross_labels:
            ax,ay=p.add(*projection.transform(lon,lat))
            text(ax,ay,name,16,'#486972',650,'text-anchor="middle" class="label"')
    for name,s in stations.items():
        pos=Point(s['xy'])
        if (not p.box.covers(pos) or not scope.covers(pos) or
                (p.name in cross_stations and name not in cross_stations[p.name][1])):
            continue
        ax,ay=p.add(*s['xy'])
        r=1.8 if p==main else 2.35
        display_name=f"{DISPLAY_NAMES.get(name,name)} · {' / '.join(s['lines'])}"
        if not s['matched']:
            display_name+=' · 出入口未接入路网'
        elif any(source=='公共通道估算' or distance>70 for _,_,source,distance in s['matched']):
            display_name+=' · 部分接驳距离估算'
        style='fill="#243f4b" stroke="#fff6ed"' if s['matched'] else 'fill="#fbfaf2" stroke="#243f4b"'
        root.append(f'<circle cx="{ax:.2f}" cy="{ay:.2f}" r="{r}" {style} stroke-width=".7"><title>{esc(display_name)}</title></circle>')
        if p.name in cross_stations:
            right = ax < p.x+p.w*.61 and name!='湖南路·安工大'
            text(ax+(7 if right else -7),ay+4,name,12,ink,600,
                 f'text-anchor="{"start" if right else "end"}" class="label"')
    for name in panel_labels.get(p.name,[]):
        location = anchor(name,p)
        if location is None:
            continue
        x,y=p.add(*location)
        text(x,y,name,(16 if name in {'秦淮区','玄武区','鼓楼区','建邺区','雨花台区'} else 20) if p==main else 18,ink,700,
             f'text-anchor="middle" class="label" data-district="{esc(name)}"')
    annotate_measure(p,10 if p==main or p.name=='S2' else 4)
    root.append('</g>')
    rect(p.x,p.y,p.w,p.h,'none','rx="4" stroke="#9fb6bc" stroke-width="1"')

x=1040
text(x,1005,'图例',20,ink,700)
rect(x,1017,22,15,coral,'rx="2"')
text(x+34,1030,'步行 ≤ 1 公里的地表范围',15,ink,650)
line(x,1052,x+22,1052,red,2)
text(x+34,1057,'步行 ≤ 1 公里的路段',15)
line(x+350,1025,x+372,1025,teal,1.85)
text(x+384,1030,'南京市界 / 区界',15)
line(x+350,1052,x+372,1052,'#7298a4',1.2,'stroke-dasharray="4 3"')
text(x+384,1057,'水上行政界线',15)
root.append(f'<circle cx="{x+10}" cy="1079" r="3.8" fill="#243f4b" stroke="#fff6ed" stroke-width=".8"/>')
text(x+34,1084,'运营车站（悬停看站名）',15)
if any(not s['matched'] for s in stations.values()):
    root.append(f'<circle cx="{x+361}" cy="1079" r="3.8" fill="#fbfaf2" stroke="#243f4b" stroke-width="1"/>')
    text(x+384,1084,'出入口未接入路网',15)
line(x,1097,1764,1097,'#cbd7d6')
for i,s in enumerate([
    '沿道路、人行道、桥和通道计算，步行可以跨越行政界线。',
    '色块按 8 米网格估算。部分站口到路网的接驳距离采用估算。',
    '南京市外只显示宁马线和宁句线外市站点周边。',
    '缺绘的站口、步道和门禁会影响局部范围。',
]):
    text(x,1119+i*22,s,15,muted)
line(x,1194,1764,1194,'#cbd7d6')
for i,(url,label) in enumerate([
    ('https://www.openstreetmap.org/copyright','© OpenStreetMap contributors · ODbL'),
    ('https://download.geofabrik.de/asia/china/','Geofabrik 江苏、安徽路网'),
    ('https://www.nanjing.gov.cn/msxx/202609/t20260929_5919052.html','南京市政府 · 地铁运营信息'),
    ('https://maps.gaode.com/ssr/subway/nanjing-3201','高德地图运营站点'),
    ('https://map.baidu.com/','百度地图补充出入口'),
    ('https://www.nanjing.gov.cn/zgnjsjb/csgk/202609/t20260929_5919738.html','南京市政府 · 行政区划'),
]):
    xl=x+(i%2)*350
    yy=1211+(i//2)*18
    root.append(f'<a href="{esc(url)}" xlink:href="{esc(url)}">')
    text(xl,yy,label,13,'#486972')
    root.append('</a>')
root.append('</svg>')
svg='\n'.join(root)
(folder/'nanjing-walk.svg').write_text(svg,encoding='utf-8')
print('Size',round(len(svg.encode('utf-8'))/1e6,2),'MB',flush=True)
