from common import *
from exit_lookup import bdmc_to_gcj

raw=json.loads((folder/'raw-exits.json').read_text(encoding='utf-8'))
existing=json.loads((folder/'exits.json').read_text(encoding='utf-8'))
station_info=json.loads((folder/'stations.json').read_text(encoding='utf-8'))
seen={r.get('uid') for r in existing}
new=[]
for name,query,results in raw:
    for result in results:
        uid=result.get('uid')
        if uid in seen:
            continue
        alias='(?:[·・]阳澄数谷)?' if name=='倪浜' else ''
        m=re.fullmatch(re.escape(name)+alias+r'地铁站[-— ]*([A-Za-z]?\d{1,2}[A-Za-z]?)(?:号)?(?:[东西南北]{1,2})?(?:出入口|出口|入口|口)',
                       result.get('name') or '')
        if not m or str(result.get('catalogID'))!='519':
            continue
        try:
            lon,lat=bdmc_to_gcj(int(result['x'])/100,int(result['y'])/100,GEO_EXTENT)
        except (KeyError,ValueError,TypeError,AssertionError):
            continue
        xy=project_gcj(lon,lat)
        if hypot(xy[0]-station_info[name]['xy'][0],xy[1]-station_info[name]['xy'][1])>490:
            continue
        row={'station':name,'exit':m.group(1).upper(),'lon':lon,'lat':lat,'crs':'gcj02','source':'百度地图','uid':uid}
        existing.append(row)
        new.append(row)
        seen.add(uid)
(folder/'exits.json').write_text(json.dumps(existing,ensure_ascii=False),encoding='utf-8')
print('Confirmed extra exits',dict(Counter(r['station'] for r in new)),flush=True)
for name,query,results in raw:
    if name in {'徐家浜','团结桥'}:
        print(name,query,[(r['name'],r['catalogID'],r['x'],r['y']) for r in results if (r['name'] or '').startswith(name)],flush=True)
