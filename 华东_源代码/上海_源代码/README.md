# 上海市地铁步行 1 公里覆盖图

本目录是上海全市版 SVG 的 Python 源码。程序从可步行的道路、桥梁和通道建立路网，从多个地铁出入口同时计算最短步行距离，并在 8 米网格上估算 1 公里覆盖面。地图包含上海 16 个市辖区的区界，并保留安亭附近的跨市步行接驳。

## 运行

1. 将原图的配套 GIS 数据解压到本目录。仓库已包含运行所需的站点 JSON，另需下表所列的路网、边界补录和陆地数据。
2. 用 64 位 Python 3.12 安装依赖并运行 `build.py`。Windows PowerShell 示例见下方。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
```

程序会生成 `shanghai-walk.svg` 和用于重跑的 `city-*.pkl` 文件。`city_qa.py` 会独立核对最短路计算、区界、主要水域和 SVG 结构。

| 文件 | 用途 |
| --- | --- |
| `shanghai.osm.pbf` | Geofabrik 的 `shanghai-261121.osm.pbf`，改名后放在 `build.py` 旁。程序使用 `shanghai.md5` 校验。 |
| `bound-jingan.osm`、`bound-baoshan.osm` | 原图使用的 OSM 边界补录，对应静安区关系 `398353`、宝山区关系 `398374`。 |
| `anting-border.osm` | 原图使用的安亭周边跨界路网补录，提取范围为东经 121.091–121.163、北纬 31.275–31.319。 |
| `ne-land/ne_10m_land.shp` | Natural Earth 1:10m 陆地数据，补充河口海岸线。 |
| `amap.json`、`supplement.json`、`hub_exits.json`、`city-exits.json` | 运营站点、补录站口和枢纽公共通道的输入。 |

## 源码入口

| 文件 | 用途 |
| --- | --- |
| `city_extract.py`、`city_boundary_fix.py` | 从快照提取道路、水域、区界及站口，修补缺少的区界成员。 |
| `city_coast.py`、`city_land_fallback.py` | 组装陆地和海岸线，供绘图裁切。 |
| `city_routes.py`、`route.py`、`stations.py` | 匹配出入口、处理通行限制并计算最短路。 |
| `city_coverage.py`、`coverage.py` | 将范围切分成瓦片，计算可达路段和估算覆盖面。 |
| `city_svg.py` | 生成包含区界、图例和放大图的 SVG。 |

路网与区界来自 OpenStreetMap，路网快照由 Geofabrik 提供。陆地底图补充使用 Natural Earth。站点与出入口参考上海地铁、高德地图和百度地图。出入口位置、缺失小路、门禁和少量站内接驳的估算会影响局部范围。 [OpenStreetMap](https://www.openstreetmap.org/copyright) · [Geofabrik 上海快照](https://download.geofabrik.de/asia/china/shanghai.html) · [Natural Earth 陆地](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/) · [上海地铁](https://service.shmetro.com/) · [高德上海地铁线网](https://www.amap.com/ssr/subway/shanghai-3100) · [百度地图](https://map.baidu.com/)
