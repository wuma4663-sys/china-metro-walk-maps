# 杭州市地铁步行 1 公里覆盖图

本项目生成杭州全市的步行覆盖 SVG。图中标出 10 个市辖区、2 个县和 1 个县级市，附中心城区放大图。杭州以外只绘制杭海城际在海宁和绍兴 1 号线（含运营支线）在绍兴的站点周边。

## 复现地图

推荐使用 64 位 Python 3.12。[下载浙江 OpenStreetMap 路网快照](https://download.geofabrik.de/asia/china/zhejiang/zhejiang-261123.osm.pbf)，把 `zhejiang-261123.osm.pbf` 放在与 `extract.py` 同级的 `hangzhou/` 目录。快照的发布方 MD5 为 `cc7f0139e15ea176a88b9629fec7bae2`。

在包含 `build.py` 的目录打开 PowerShell，执行以下命令。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
```

快照保存在其他位置时，可以执行 `python build.py --zhejiang D:/data/zhejiang-261123.osm.pbf`。安装依赖及下载快照后，构建过程可以离线运行。程序校验输入，重建步行路网和覆盖面，最后生成并校验 `hangzhou/hangzhou-walk.svg`。再次运行会覆盖生成的 SVG 和 `.pkl` 中间文件。

## 计算口径

- 从已运营站点的公开出入口出发，在道路、人行道、桥梁与通道上计算最短步行距离。路径可以穿过行政界线。
- 深红线显示步行距离不超过 1 公里的路段。珊瑚红色块按 8 米地表网格估算覆盖范围。
- 部分站口到路网的接驳距离采用估算，包括杭州南站东广场、杭州西站换乘区和绍兴北站南广场的公共通道。站口、步道和门禁资料的缺绘会影响局部边界。在 SVG 中悬停可查看车站名和接驳说明。 [杭州南站接驳](https://www.hzzx.gov.cn/cshz/content/2020-07/10/content_7771707_0.htm) · [杭州西站换乘](https://www.hzzx.gov.cn/cshz/content/2022-09/22/content_8359495.htm) · [绍兴北站综合交通枢纽](https://www.bjucd.com/plus/view.php?aid=8122)

## 源文件

| 文件 | 用途 |
| --- | --- |
| `build.py` | 执行完整构建和校验 |
| `hangzhou/extract.py` | 提取步行路网、水域、行政边界和站口 |
| `stations.py`、`hangzhou/common.py` | 匹配站点及出入口、转换坐标、确定展示范围 |
| `route.py`、`hangzhou/route_hangzhou.py` | 处理步行权限和站口接驳，计算最短步行距离 |
| `coverage.py`、`hangzhou/tiles.py` | 生成步行覆盖面和可达路段 |
| `hangzhou/draw.py`、`hangzhou/qa.py` | 绘制 SVG，独立核对最短路、行政边界及跨市范围 |

## 数据来源

- 道路、水域、行政边界和部分站口来自 OpenStreetMap，使用 Geofabrik 浙江路网快照。行政分区按杭州市行政区划核对。 [OpenStreetMap 版权与许可](https://www.openstreetmap.org/copyright) · [Geofabrik 浙江](https://download.geofabrik.de/asia/china/zhejiang/) · [杭州市行政区划](https://zfgb.hangzhou.gov.cn/18/106220253/t106220253064/528872.shtml)
- `hangzhou/amap.json` 保存计算所需的运营线路和站点坐标。输入坐标按 GCJ-02 处理，距离计算采用以东经 120° 为中央经线的横轴墨卡托投影。 [高德杭州线网](https://m.amap.com/service/subway/hangzhou/) · [杭海城际运营信息](https://zjic.zj.gov.cn/zkdt/rdzx/202106/t20210629_6513979.shtml) · [绍兴 1 号线支线运营信息](https://www.bjucd.com/plus/view.php?aid=8121)
- `hangzhou/exits.json` 和补充站口文件保存查得的公开出入口位置。 [百度地图](https://map.baidu.com/)
