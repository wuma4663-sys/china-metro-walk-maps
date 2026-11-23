from common import *
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
import subprocess

missing=['倪浜','新郭','横塘','西津桥','马运路','团结桥','徐家浜','虎北路','古香圩']
queries=[(n,q) for n in missing for q in [f'{n}地铁站出入口',f'{n}站出口',f'{n}地铁站1口']]

def fetch(spec):
    name,q=spec
    u='https://map.baidu.com/?'+urlencode({'qt':'s','wd':q,'c':224,'rn':25})
    r=subprocess.run(['curl.exe','-fLsS','--max-time','12',u],capture_output=True)
    try:
        c=json.loads(r.stdout).get('content')
    except ValueError:
        return name,q,[]
    if not isinstance(c,list):
        return name,q,[]
    hits=[{k:x.get(k) for k in ('name','catalogID','x','y','uid','addr','std_tag')}
          for x in c if isinstance(x,dict)]
    return name,q,hits

with ThreadPoolExecutor(max_workers=4) as pool:
    result=list(pool.map(fetch,queries))
(folder/'raw-exits.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
for name,q,hits in result:
    print(q,[(v['name'],v['catalogID']) for v in hits[:12]],flush=True)
