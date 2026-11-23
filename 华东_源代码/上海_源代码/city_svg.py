import html
import math
from datetime import datetime,timedelta,timezone

from coverage import pieces
from city_stations import get_inputs
from city_routes import load_model
from stations import projection
from extract_imports import *

stamp,districts,points,ways,polys,relations,coast,basemap = get_inputs()
city,stations,_,_,_,_,_,_,contribution = load_model()
with (work/'city-coverage.pkl').open('rb') as f:
    tiles = pickle.load(f)
with (work/'city-final-land.pkl').open('rb') as f:
    land, land_source = pickle.load(f)

WIDTH,HEIGHT = 1810,1242
ink,muted,teal = '#1b3844','#536970','#244c5b'
water ='#dfedf2'
coral, red = '#fa806b','#bf3e31'
paper, map_land, city_land = '#faf9f5','#edece4','#fcfbf2'
U0,V0 = 289000,3533000
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


main=Panel('city',46,190,1075,1002,(355000,3460800),141500)
detail=Panel('center',1150,190,614,573,(352950,3458400),23750)
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


rendered_districts = {n:(i,g.intersection(main_geom)) for n,(i,g) in districts.items()}
shanghai_land=land.intersection(city).intersection(main_geom)
basemap_land=land.intersection(main_geom)
shanghai_land_prepared = shapely.prepare(shanghai_land)
display_borders=shapely.union_all([g.boundary.intersection(main_geom) for _,g in districts.values()])
city_border = city.boundary.intersection(main_geom)
dry_limits = land.buffer(70)

root.append('<?xml version="1.0" encoding="UTF-8"?>')
root.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">')
root.append('<title id="title">上海市地铁步行一公里覆盖图</title>')
root.append('<desc id="desc">上海全市十六个区的运营地铁步行一公里覆盖图。珊瑚红色块是基于最短步行路网距离和八米地表网格的估计，深红线表示可达步行路段。右侧是中心城区放大图。边界按上海本地市域和近岸图幅显示。</desc>')
root.append(f'<metadata>Road and district data: OpenStreetMap contributors, ODbL, https://www.openstreetmap.org/copyright. Geofabrik snapshot {esc(stamp)}. Basemap shoreline: {esc(land_source)}. WGS84/UTM 51N. Maximum walking network distance 1000 m. Surface estimate grid 8 m. The map frame includes the local Shanghai municipality and nearshore waters.</metadata>')
root.append('<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC","PingFang SC","Source Han Sans SC",sans-serif} .label {paint-order:stroke fill;stroke:#fcfcf7;stroke-width:3.4;stroke-linejoin:round} a text{text-decoration:underline}</style>')
root.append('<defs>')
for p in (main,detail):
    root.append(f'<clipPath id="{p.name}-clip"><rect x="{p.x}" y="{p.y}" width="{p.w}" height="{p.h}" rx="4"/></clipPath>')
add_def('base-land',[basemap_land],'Polygon',21)
add_def('shanghai-land',[shanghai_land],'Polygon',16)
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
text(46,42,'上海市',18,'#456370',600)
text(43,105,'地铁步行一公里覆盖图',56,ink,700)
text(47,140,'按步行路网到最近运营车站出入口的最短距离计算',18,muted)
local_date=datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).date().isoformat()
text(1764,45,f'路网快照  {local_date}',16,'#546c72',500,'text-anchor="end"')
text(1764,82,'16 个行政区',21,ink,700,'text-anchor="end"')
line(46,154,1764,154,'#cbd7d6')
text(46,179,'全市总览',19,ink,700)
text(1150,179,'中心城区放大',19,ink,700)


all_labels = {
 '崇明区': (121.564,31.664), '宝山区':(121.407,31.418), '嘉定区':(121.231,31.402),
 '青浦区':(121.084,31.141),'松江区':(121.222,30.998),'金山区':(121.183,30.847),
 '奉贤区':(121.526,30.887),'闵行区':(121.402,31.056),'浦东新区':(121.737,31.119),
 '普陀区':(121.389,31.248),'长宁区':(121.365,31.218),'徐汇区':(121.436,31.167),
 '静安区':(121.450,31.276),'虹口区':(121.503,31.277),'杨浦区':(121.547,31.296),
 '黄浦区':(121.487,31.212),
}
central={'普陀区','长宁区','徐汇区','静安区','虹口区','杨浦区','黄浦区'}
panel_labels={'city':[n for n in all_labels if n not in central],
              'center':[n for n in all_labels if n in central]}
shore_labels=[
    ('长江口',122.10,31.568),('杭州湾',121.617,30.730),('东海',122.033,30.944),
    ('江苏省',121.029,31.450),('浙江省',120.992,30.839),
    ('长兴岛',121.699,31.400),('横沙岛',121.846,31.338),
]


def anchor(name):
    reference=Point(projection.transform(*all_labels[name]))
    geom=districts[name][1]
    if geom.covers(reference):
        return tuple(reference.coords)[0]
    print('Label point on district border',name,flush=True)
    return tuple(max(pieces(geom.intersection(main_geom),'Polygon'),key=lambda p:p.area).representative_point().coords)[0]


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


for p in (main,detail):
    root.append(f'<g clip-path="url(#{p.name}-clip)">')
    rect(p.x,p.y,p.w,p.h,water)
    p.place('base-land',f'fill="{map_land}" fill-rule="evenodd"')
    p.place('shanghai-land',f'fill="{city_land}" fill-rule="evenodd"')
    p.place('parks','fill="#dce8d5" fill-rule="evenodd" opacity=".66"')
    use_lines(p,'waterline','#c8dce2',.62)
    p.place('water-area','fill="#d4e7ee" fill-rule="evenodd"')
    if p==detail:
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
    if p==main:
        ll,bot,rr,top=detail.box.bounds
        x,y=p.add(ll,top)
        w,h=(rr-ll)*p.scale,(top-bot)*p.scale
        rect(x,y,w,h,'none','stroke="#537178" stroke-width="1.05" stroke-dasharray="4 4"')
        for name,lon,lat in shore_labels:
            ax,ay=p.add(*projection.transform(lon,lat))
            text(ax,ay,name,16,'#68838b',500,'text-anchor="middle" class="label" letter-spacing="1.3"')
    for name,s in stations.items():
        pos=Point(s['xy'])
        if not p.box.covers(pos) or (not city.covers(pos) and not s['matched']):
            continue
        ax,ay=p.add(*s['xy'])
        r=1.8 if p==main else 2.35
        display_name=f"{name} · {' / '.join(s['lines'])}"
        if not s['matched']:
            display_name+=' · 出入口未接入路网'
        style='fill="#243f4b" stroke="#fff6ed"' if s['matched'] else 'fill="#fbfaf2" stroke="#243f4b"'
        root.append(f'<circle cx="{ax:.2f}" cy="{ay:.2f}" r="{r}" {style} stroke-width=".7"><title>{esc(display_name)}</title></circle>')
    for name in panel_labels[p.name]:
        x,y=p.add(*anchor(name))
        text(x,y,name,21 if p==main else 19,ink,700,
             f'text-anchor="middle" class="label" data-district="{esc(name)}"')
    annotate_measure(p,10 if p==main else 2)
    root.append('</g>')
    rect(p.x,p.y,p.w,p.h,'none','rx="4" stroke="#9fb6bc" stroke-width="1"')

x=1150
text(x,799,'图例',24,ink,700)
rect(x,820,22,15,coral,'rx="2"')
text(x+34,833,'步行 ≤ 1 公里的地表范围',16,ink,650)
line(x,854,x+22,854,red,2)
text(x+34,859,'步行 ≤ 1 公里的路段',15)
line(x+330,828,x+352,828,teal,1.85)
text(x+364,833,'市界 / 区界',15)
line(x+330,854,x+352,854,'#7298a4',1.2,'stroke-dasharray="4 3"')
text(x+364,859,'近岸水上界线',15)
root.append(f'<circle cx="{x+10}" cy="881" r="3.8" fill="#243f4b" stroke="#fff6ed" stroke-width=".8"/>')
text(x+34,886,'运营车站（悬停看站名）',15)
root.append(f'<circle cx="{x+341}" cy="881" r="3.8" fill="#fbfaf2" stroke="#243f4b" stroke-width="1"/>')
text(x+364,886,'出入口未接入路网',15)
line(x,906,1764,906,'#cbd7d6')
text(x,935,'读图说明',21,ink,700)
for i,s in enumerate([
    '沿道路、人行道、桥和通道计算，区界不截断步行路径。',
    '色块按 8 米网格估算，路网、出入口和门禁漏绘会影响局部结果。',
    '含浦江线、磁浮线和市域机场线。机场枢纽使用公共通道接点。',
    '图幅展示上海本地市域及近岸区界。',
]):
    text(x,963+i*24,s,16,muted)
line(x,1059,1764,1059,'#cbd7d6')
text(x,1086,'数据来源',17,ink,700)
for i,(url,label) in enumerate([
    ('https://www.openstreetmap.org/copyright','© OpenStreetMap contributors · ODbL'),
    ('https://download.geofabrik.de/asia/china/shanghai.html','Geofabrik 上海路网快照'),
    ('https://service.shmetro.com/','上海地铁运营及出入口资料'),
    ('https://www.amap.com/ssr/subway/shanghai-3100','高德地图运营站点'),
    ('https://map.baidu.com/','百度地图补充出入口'),
    ('https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/','Natural Earth 陆地底图'),
]):
    xl=x+(i%2)*330
    yy=1113+(i//2)*24
    root.append(f'<a href="{esc(url)}" xlink:href="{esc(url)}">')
    text(xl,yy,label,13,'#486972')
    root.append('</a>')
root.append('</svg>')
svg='\n'.join(root)
(work/'shanghai-walk.svg').write_text(svg,encoding='utf-8')
print('Size',round(len(svg.encode('utf-8'))/1e6,2),'MB',flush=True)
