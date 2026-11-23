"""从 OSM 快照生成南京地铁步行覆盖图并执行校验。"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent
    data = project / "nanjing"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jiangsu", type=Path, default=data / "jiangsu-261122.osm.pbf")
    parser.add_argument("--anhui", type=Path, default=data / "anhui-261122.osm.pbf")
    args = parser.parse_args()
    snapshots = {
        "jiangsu": args.jiangsu.resolve(),
        "anhui": args.anhui.resolve(),
    }
    for path in snapshots.values():
        if not path.is_file():
            parser.error(f"找不到路网快照 {path}。请按 README 下载相应文件。")

    def run(script, *arguments):
        print(f"\nRunning {script} {' '.join(map(str, arguments))}", flush=True)
        subprocess.run(
            [sys.executable, "-u", str(data / script), *map(str, arguments)],
            cwd=project,
            check=True,
        )

    for province, path in snapshots.items():
        run("extract.py", province, path)
    run("gulou_boundary.py", snapshots["jiangsu"])
    for script in ("route_nanjing.py", "tiles.py", "draw.py", "qa.py"):
        run(script)
    print(f"\nSVG {data / 'nanjing-walk.svg'}", flush=True)


if __name__ == "__main__":
    main()
