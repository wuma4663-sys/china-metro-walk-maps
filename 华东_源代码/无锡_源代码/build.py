"""从江苏 OpenStreetMap 快照生成并校验无锡地铁步行覆盖图。"""

import argparse
from pathlib import Path
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parent
    data = project / "wuxi"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jiangsu", type=Path, default=data / "jiangsu-261122.osm.pbf")
    snapshot = parser.parse_args().jiangsu.resolve()
    if not snapshot.is_file():
        parser.error(f"找不到路网快照 {snapshot}。请按 README 下载对应文件。")

    stages = [
        ("extract.py", snapshot),
        ("route_wuxi.py",),
        ("estimate.py",),
        ("tiles.py", "--verified"),
        ("tiles.py",),
        ("draw.py",),
        ("qa.py",),
    ]
    for script, *arguments in stages:
        subprocess.run(
            [sys.executable, "-u", str(data / script), *map(str, arguments)],
            cwd=project,
            check=True,
        )
    print(data / "wuxi-walk.svg")


if __name__ == "__main__":
    main()
