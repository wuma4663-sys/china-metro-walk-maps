"""Generate the Shanghai walking coverage SVG from the archived inputs."""

import subprocess
import sys
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent
    inputs = (
        "shanghai.osm.pbf",
        "bound-jingan.osm",
        "bound-baoshan.osm",
        "anting-border.osm",
        "ne-land/ne_10m_land.shp",
        "amap.json",
        "supplement.json",
        "hub_exits.json",
        "city-exits.json",
    )
    missing = [name for name in inputs if not (project / name).is_file()]
    if missing:
        raise SystemExit("请按 README.md 准备以下文件：\n" + "\n".join(missing))

    for script in (
        "city_extract.py",
        "city_land_fallback.py",
        "city_routes.py",
        "city_coverage.py",
        "city_svg.py",
        "city_qa.py",
    ):
        print(f"\nRunning {script}", flush=True)
        subprocess.run([sys.executable, "-X", "utf8", "-u", str(project / script)], cwd=project, check=True)

    print(f"\nSVG: {project / 'shanghai-walk.svg'}")


if __name__ == "__main__":
    main()
