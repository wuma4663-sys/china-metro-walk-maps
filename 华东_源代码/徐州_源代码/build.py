"""用 Geofabrik 江苏路网快照生成徐州市地铁步行一公里覆盖图。"""

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jiangsu', type=Path, default=root / 'jiangsu-261122.osm.pbf')
    parser.add_argument('--output', type=Path, default=root / 'xuzhou-metro-walk-1km.svg')
    args = parser.parse_args()
    snapshot, output = args.jiangsu.resolve(), args.output.resolve()
    if not snapshot.is_file():
        parser.error(f'找不到江苏 OSM 快照：{snapshot}')

    with snapshot.open('rb') as stream:
        print('Jiangsu SHA-256', hashlib.file_digest(stream, 'sha256').hexdigest(), flush=True)
    for module, arguments in (
        ('extract_xuzhou.py', [snapshot]), ('route_xuzhou.py', []),
        ('tiles_xuzhou.py', []), ('draw_xuzhou.py', [output]),
    ):
        subprocess.run([sys.executable, '-X', 'utf8', '-u', str(root / module), *map(str, arguments)],
                       cwd=root, check=True)


if __name__ == '__main__':
    main()
