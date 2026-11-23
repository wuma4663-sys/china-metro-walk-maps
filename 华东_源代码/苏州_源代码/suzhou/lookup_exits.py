import argparse
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from common import *
from exit_lookup import bdmc_to_gcj

OUTPUT = folder/'exits.json'


def fetch(query):
    station,ref,center,city_code=query
    target=station+'地铁站'+(ref+'口' if ref else '出入口')
    qry=urlencode({'qt':'s','wd':target,'c':city_code,'rn':25})
    result=subprocess.run(['curl.exe','-fLsS','--max-time','9','https://map.baidu.com/?'+qry],
                          capture_output=True,check=False)
    if result.returncode:
        return []
    try:
        names=json.loads(result.stdout).get('content')
    except ValueError:
        return []
    if not isinstance(names,list):
        return []
    found=[]
    prefix=station+'地铁站'
    for x in names:
        if not isinstance(x,dict):
            continue
        poi=x.get('name') or ''
        if not poi.startswith(prefix):
            continue
        suffix=poi[len(prefix):].strip(' -—')
        match=re.fullmatch(r'([A-Z]?\d{1,2}[A-Z]?|[A-Z]{1,2}|[东西南北][A-Z]?\d?)(?:号)?(?:出入口|入口|出口|口)',suffix,re.I)
        if not match:
            continue
        if str(x.get('catalogID'))!='519' and (not suffix.endswith(('入口','出口')) or '在建' in poi):
            continue
        code=match.group(1).upper()
        if ref and code!=ref and not code.startswith(ref):
            continue
        try:
            lon,lat=bdmc_to_gcj(int(x['x'])/100,int(x['y'])/100,GEO_EXTENT)
        except (KeyError,ValueError,AssertionError,TypeError):
            continue
        if hypot(lon-center[0],lat-center[1])>.008:
            continue
        found.append({'station':station,'exit':code,'lon':lon,'lat':lat,'crs':'gcj02','source':'百度地图','uid':x.get('uid')})
    time.sleep(.20)
    return found


def names_and_centers():
    unique={}
    for route in sources()['l']:
        city_code=317 if route['ln'].startswith('无锡') else 224
        if city_code==317 and '--fallback' not in sys.argv:
            continue
        for station in route['st']:
            if station['n'] not in unique:
                unique[station['n']]=(tuple(map(float,station['sl'].split(','))),city_code)
    return unique


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--fallback',action='store_true')
    p.add_argument('--station',action='append',default=[])
    args=p.parse_args()
    existing=json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else []
    names=names_and_centers()
    if args.station:
        jobs=[(name,code,*names[name]) for name in args.station if name in names
              for code in ('1','2','3','4','A','B')]
    elif args.fallback:
        statuses=json.loads((folder/'stations.json').read_text(encoding='utf-8'))
        eligible = {name for name,s in statuses.items() if
                    s['border_distance']<=1050 and (not s['exits'] or
                    (len(s['exits'])==1 and not any(r['station']==name for r in existing)))}
        jobs=[(name,code,*names[name]) for name in sorted(eligible) if name in names for code in ('1','2','3','4','A','B')]
    else:
        jobs=[(name,'',*xy) for name,xy in names.items()]
    print('Exit queries',len(jobs),flush=True)
    seen={r.get('uid'):(r['station'],r.get('exit')) for r in existing if r.get('uid')}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,items in enumerate(pool.map(fetch,jobs),1):
            for row in items:
                if row.get('uid') and row['uid'] in seen:
                    continue
                seen[row.get('uid')]=(row['station'],row['exit'])
                existing.append(row)
            if i%40==0:
                print(i,'queries checked,',len(existing),'exit POIs',flush=True)
    staged=OUTPUT.with_suffix('.json.tmp')
    staged.write_text(json.dumps(existing,ensure_ascii=False),encoding='utf-8')
    staged.replace(OUTPUT)
    print('Exit POIs',len(existing),'for',len({r['station'] for r in existing}),'stations',flush=True)
