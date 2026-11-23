import json
import re
import sys
from pathlib import Path

folder = Path(__file__).parent
sys.path.insert(0,str(folder.parent))
from extract_imports import *
from stations import real_stations, project_gcj, projection

DISTRICTS = {
    '虎丘区','吴中区','相城区','姑苏区','吴江区','常熟市','张家港市','昆山市','太仓市',
}
PARK = '苏州工业园区'
GEO_EXTENT = (119.80,30.62,121.55,32.25)


def sources():
    source = json.loads((folder/'amap.json').read_text(encoding='utf-8'))
    for line in source['l']:
        for s in line['st']:
            s['n']=re.sub(r'\([^)]*\)$','',s['n'])
    shanghai = json.loads((folder.parent/'amap.json').read_text(encoding='utf-8'))
    branch = [s for line in shanghai['l'] if line['ln']=='11号线' for s in line['st']
              if s['n'] in {'安亭','兆丰路','光明路','花桥'}]
    source['l'].append({'ln':'上海11号线','st':branch})
    wuxi_file = folder/'wuxi-amap.json'
    if wuxi_file.exists():
        for line in json.loads(wuxi_file.read_text(encoding='utf-8'))['l']:
            line['ln']='无锡'+line['ln']
            source['l'].append(line)
    return source


def read_model():
    with (folder/'extract.pkl').open('rb') as file:
        return pickle.load(file)


def select_stations(nodes,ways,relations,city):
    return real_stations(nodes,ways,relations,city,map_data=sources(),
                         supplemental_files=[folder/'exits.json',folder/'verified-exits.json'],
                         hub_access_enabled=False,max_entrance_distance=390)
