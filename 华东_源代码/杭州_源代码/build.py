"""根据浙江 OSM 快照重建杭州地铁步行覆盖 SVG。"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent
    data = project / "hangzhou"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zhejiang", type=Path, default=data / "zhejiang-261123.osm.pbf")
    snapshot = parser.parse_args().zhejiang.resolve()
    if not snapshot.is_file():
        parser.error(f"找不到路网快照 {snapshot}。请按 README 下载相应文件。")

    steps = (
        ("extract.py", str(snapshot)),
        ("route_hangzhou.py",),
        ("tiles.py",),
        ("draw.py",),
        ("qa.py",),
    )
    for script, *arguments in steps:
        print(f"\nRunning {script}", flush=True)
        subprocess.run(
            [sys.executable, "-u", str(data / script), *arguments],
            cwd=project,
            check=True,
        )
    print(f"\nSVG {data / 'hangzhou-walk.svg'}", flush=True)


if __name__ == "__main__":
    main()
