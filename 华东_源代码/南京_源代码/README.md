# 南京市地铁步行 1 公里覆盖图

本项目生成 2026 年 11 月 23 日版南京地铁步行覆盖 SVG。图中带有南京 11 个区的边界、中心城区放大图，以及 S2 宁马线马鞍山段和 S6 宁句线镇江句容段的站点周边图。南京市外其余区域留白。

## 复现地图

推荐使用 64 位 Python 3.12。先下载以下两个 OpenStreetMap 路网快照，按原文件名放入与 `extract.py` 同级的 `nanjing/` 目录。

| 路网快照 | 发布方 MD5 |
| --- | --- |
| [jiangsu-261122.osm.pbf](https://download.geofabrik.de/asia/china/jiangsu/jiangsu-261122.osm.pbf)（江苏） | `5941a77477c0aa7bd8ff332caca96863` |
| [anhui-261122.osm.pbf](https://download.geofabrik.de/asia/china/anhui/anhui-261122.osm.pbf)（安徽） | `d126102145d9d2aa0a61274571664024` |

在包含 `build.py` 的目录打开 PowerShell，运行以下命令。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
```

快照保存在其他位置时，用 `--jiangsu` 和 `--anhui` 指定路径，例如 `python build.py --jiangsu D:/data/jiangsu.osm.pbf --anhui D:/data/anhui.osm.pbf`。安装依赖及下载快照后，构建过程可以离线运行。程序会校验两个快照的 MD5，依次计算并校验结果，生成 `nanjing/nanjing-walk.svg`。再次运行会覆盖该 SVG 及生成的 `.pkl` 中间文件。

## 计算口径

- 根据已运营地铁站点和公开出入口，在道路、人行道、桥梁和通道上计算到最近地铁出入口的最短步行距离。区界和市界只用于显示，步行路径可跨越行政界线。
- 深红线为计算距离不超过 1 公里的步行路段。珊瑚红色块根据这些路段和附近地表的通行条件按 8 米网格估算。
- 部分站口至步行路网的接驳距离采用估算，包括太白站和金马路站。缺绘的站口、步道和门禁会影响局部范围。市外只绘制两条跨市运营线路的外市站点周边。

## 源文件

| 文件 | 用途 |
| --- | --- |
| `build.py` | 运行完整构建和校验 |
| `nanjing/extract.py`、`nanjing/gulou_boundary.py` | 提取路网、水域、行政边界和站口，复现发布图中的鼓楼区界线 |
| `stations.py`、`nanjing/common.py` | 匹配站点和出入口、转换坐标、确定制图范围 |
| `route.py`、`nanjing/route_nanjing.py` | 处理步行权限和站口接驳，计算最短步行距离 |
| `coverage.py`、`nanjing/tiles.py` | 生成步行覆盖面和可达路段 |
| `nanjing/draw.py` | 绘制 SVG |
| `nanjing/qa.py` | 独立核对最短路、11 区边界、跨市站点和 SVG 结构 |

## 数据来源

- 道路、水域、边界和部分出入口来自 OpenStreetMap，使用 Geofabrik 江苏及安徽快照。OpenStreetMap 数据采用 ODbL。 [OpenStreetMap 版权与许可](https://www.openstreetmap.org/copyright) · [Geofabrik 中国下载页](https://download.geofabrik.de/asia/china/)
- `nanjing/amap.json` 保存计算用的运营线路和站点坐标。输入坐标按 GCJ-02 处理，距离计算采用 UTM 50N。 [高德南京地铁线网](https://maps.gaode.com/ssr/subway/nanjing-3201) · [南京市政府运营信息](https://www.nanjing.gov.cn/msxx/202609/t20260929_5919052.html)
- `nanjing/exits.json` 和 `nanjing/verified-exits.json` 保存用于补充的公开站口坐标。 [百度地图](https://map.baidu.com/)
