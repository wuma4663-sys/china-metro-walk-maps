import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from pathlib import Path

work = Path(__file__).parent
official_path = work/'official'/'subway-shanghai-master'/'src'/'data'/'stationInfo.json'
official = {x.get('name_cn'):x for x in json.loads(official_path.read_text(encoding='utf-8')).values()}


def bdmc_to_gcj(x, y, extent=(120.8,30.7,122,31.7)):
    if y >= 3481989.83:
        cs = [-1.981981304930552e-8,.000008983055099779535,.03278182852591,40.31678527705744,
              .65659298677277,-4.44255534477492,.85341911805263,.12923347998204,-.04625736007561,4482777.06]
    else:
        cs = [3.09191371068437e-9,.000008983055096812155,.00006995724062,23.10934304144901,
              -.00023663490511,-.6321817810242,-.00663494467273,.03430082397953,-.00466043876332,2555164.4]
    bd_lon = cs[0] + cs[1]*x
    bd_lat = sum(c*(y/cs[-1])**i for i,c in enumerate(cs[2:-1]))
    lon, lat = bd_lon - .0065, bd_lat - .006
    factor = math.pi*3000/180
    z = math.hypot(lon,lat) - .00002*math.sin(lat*factor)
    theta = math.atan2(lat,lon) - .000003*math.cos(lon*factor)
    coord = z*math.cos(theta), z*math.sin(theta)
    assert extent[0] < coord[0] < extent[2] and extent[1] < coord[1] < extent[3], coord
    return coord


def key(ref):
    return ref.replace('号','').replace('出入口','').replace('出口','').replace('口','').strip()


jobs = {}
for line in (work/'station-list.txt').read_text(encoding='utf-8-sig').splitlines():
    name, lines, distance, data = line.split(' ',3)
    if int(distance)>1450:
        continue
    recorded = {key(s.partition(' ')[2]) for s in data.partition(' ')[2].split(' | ')}
    info = official.get(name, official.get(name.replace('·','・'), {}))
    refs = {key(a.split(':')[0]) for a in re.split(r'<br\s*/?>',info.get('entranceInfo','')) if ':' in a}
    refs = {r for r in refs if re.fullmatch(r'[北南东西]?[A-Z]?\d{1,2}[A-Z]?',r)}
    if name in ('虹桥2号航站楼','虹桥火车站'):
        continue
    if name == '莘庄':
        recorded.add('北1')
    if name == '国家会展中心':
        recorded.update({'2','3'})
    refs = refs - recorded
    if refs:
        jobs[name] = sorted(refs)


def fetch(job):
    name, number = job
    q = name+'地铁站'+number+'口'
    query = urlencode({'qt':'s','wd':q,'c':289,'rn':10})
    url = 'https://map.baidu.com/?'+query
    try:
        raw = subprocess.run(['curl.exe','-fLsS','--max-time','10',url], check=True, capture_output=True).stdout
        payload = json.loads(raw)
    except (ValueError, subprocess.CalledProcessError):
        return name,number,None
    content = payload.get('content') or []
    if isinstance(content,dict):
        content = [content]
    for x in content:
        if not isinstance(x,dict):
            continue
        poi = x.get('name','')
        if (str(x.get('catalogID'))=='519' and poi.startswith(name) and
            key(re.sub(r'^.*?(?:地铁站|地铁|站)[-—\s]*','',poi))==number):
            lon,lat = bdmc_to_gcj(int(x['x'])/100,int(x['y'])/100)
            return name,number,{'station':name,'exit':number,'lon':lon,'lat':lat,'crs':'gcj02','source':'百度地图','uid':x['uid']}
    return name,number,None


if __name__ == '__main__':
    print('Jobs',len(jobs),sum(map(len,jobs.values())),jobs,flush=True)
    rows = []
    missing = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for name,number,row in executor.map(fetch,[(a,b) for a,bb in jobs.items() for b in bb]):
            if row:
                rows.append(row)
            else:
                missing.append((name,number))
    (work/'supplement.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Confirmed:',len(rows),'missing:',len(missing),missing,flush=True)
