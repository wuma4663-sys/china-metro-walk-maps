# 苏州市地铁步行 1 公里覆盖图

这份源码用于复现 2026 年 11 月 23 日交付的苏州全市 SVG。程序从可步行的道路、桥梁和通道构建路网，用多源最短路径计算到最近运营地铁出入口的距离，再把 1 公里内的路段和估算覆盖范围画在图上。

## 在 Windows 上运行

1. 解压源码 ZIP。推荐使用 64 位 Python 3.12，本次复验使用 3.12.14。
2. 下载随源码交付的 `jiangsu-verified.osm.pbf`，放进解压目录下的 `suzhou` 子文件夹，与 `extract.py` 放在一起。若使用 Geofabrik 原始快照 `jiangsu-261122.osm.pbf`，放进去前请改成 `jiangsu-verified.osm.pbf`。程序会检查文件大小和发布方的 MD5。
3. 在解压目录的文件资源管理器地址栏输入 `powershell` 并按回车。在打开的 PowerShell 里依次运行以下命令。安装依赖需要联网，后续计算可离线完成。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
```

完成后打开 `suzhou/suzhou-walk.svg`。程序会在同一目录生成 `extract.pkl`、`routes.pkl` 和 `coverage.pkl`。再次运行会重新生成这些文件以及 SVG。

## 源码位置

| 文件 | 用途 |
| --- | --- |
| `build.py` | 依次执行提取、计算、绘图和校验 |
| `suzhou/extract.py` | 提取步行路网、水域、市界及区界 |
| `stations.py`、`suzhou/common.py` | 整理运营站点，匹配 OSM 和补录出入口，转换坐标 |
| `route.py`、`suzhou/route_suzhou.py` | 建立步行图，处理站口接驳和通行约束，计算步行距离 |
| `coverage.py`、`suzhou/tiles.py` | 按 8 米网格估算覆盖面 |
| `suzhou/draw.py` | 写出含区界、图例和中心城区放大图的矢量 SVG |
| `suzhou/qa.py` | 独立核对最短路结果、覆盖边界及 SVG 结构 |

`suzhou/prepare.py`、`suzhou/lookup_exits.py`、`suzhou/raw_exits.py`、`suzhou/import_confirmed.py` 和 `suzhou/check_gaps.py` 是当时补录和核对地铁出入口的辅助脚本。正常复现直接使用包内的 `suzhou/exits.json`，无需重新查询在线地图。

## 数据来源与口径

- 路网、市界和区界来自 OpenStreetMap，采用 Geofabrik 江苏 `jiangsu-261122.osm.pbf` 快照。快照 MD5 为 `5941a77477c0aa7bd8ff332caca96863`。路网数据按 ODbL 提供。 [Geofabrik 江苏](https://download.geofabrik.de/asia/china/jiangsu.html) · [OpenStreetMap 版权与许可](https://www.openstreetmap.org/copyright)
- `suzhou/amap.json`、`suzhou/wuxi-amap.json` 和根目录的 `amap.json` 保留计算所需的线路和站点字段。根目录的文件只包含上海 11 号线跨界段所需站点。高德站点坐标按 GCJ-02 处理。 [高德苏州地铁线网](https://www.amap.com/ssr/subway/suzhou-3205) · [苏州市政府运营信息](https://www.suzhou.gov.cn/szsrmzf/mszx/202609/b6c7158ce0d24c4fb6a1c429866f60f8.shtml)
- `suzhou/exits.json` 保存百度地图补录的站口。苏州火车站南广场等少量接驳在代码中估算。覆盖面精度受出入口、步行路网和门禁资料完整性影响。 [百度地图](https://map.baidu.com/)
