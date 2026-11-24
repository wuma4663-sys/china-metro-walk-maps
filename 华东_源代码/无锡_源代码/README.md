# 无锡市地铁步行 1 公里覆盖图

地图使用截至 2026 年 11 月 24 日运营的 1–4 号线和 S1 线，共 89 座车站。图中保留无锡 5 个市辖区、江阴和宜兴的行政区界，并附中心城区和江阴城区放大图。

## 复现地图

使用 64 位 Python 3.12。从 Geofabrik 下载 [江苏路网快照 jiangsu-261122.osm.pbf](https://download.geofabrik.de/asia/china/jiangsu/jiangsu-261122.osm.pbf)。发布方提供的 MD5 为 `5941a77477c0aa7bd8ff332caca96863`。将快照放在 `wuxi/` 下，或通过 `--jiangsu` 指定位置。

在本目录打开 PowerShell，运行以下命令。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
```

程序先校验路网快照，再提取道路、水体、站口和行政区界，计算步行路网，最后生成并校验 `wuxi/wuxi-walk.svg`。安装依赖和取得快照后可离线运行。

## 计算口径

- 路段按到最近站口的最短可步行距离计算，阈值为 1,000 米。行政区界用于制图，计算路径可跨区。
- 珊瑚红色块源自有坐标的站口，浅橙色块源自 34 座站的估算接驳点。浅橙色范围随实际站口位置、路网完整性和通行条件变化。
- 地表色块按 8 米网格估算。路网快照来自 [OpenStreetMap](https://www.openstreetmap.org/copyright)，采用 ODbL。运营车站和站点坐标来自 [高德无锡地铁线网](https://maps.gaode.com/ssr/subway/wuxi-3202)，距离以 WGS 84 / UTM 51N 米制坐标计算。
