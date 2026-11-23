"""Regenerate the Suzhou walking coverage SVG and run its checks."""

import subprocess
import sys
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent
    data = project / "suzhou"
    snapshot = data / "jiangsu-verified.osm.pbf"
    if not snapshot.is_file():
        raise SystemExit(f"请把配套路网快照放在这里：{snapshot}")

    for script in ("extract.py", "route_suzhou.py", "tiles.py", "draw.py", "qa.py"):
        print(f"\nRunning {script}", flush=True)
        subprocess.run([sys.executable, "-u", str(data / script)], cwd=project, check=True)

    print(f"\nSVG: {data / 'suzhou-walk.svg'}")


if __name__ == "__main__":
    main()
