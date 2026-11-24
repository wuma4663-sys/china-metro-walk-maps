# 徐州市地铁步行一公里覆盖图

本图包括徐州市全域总览和运营线网覆盖区放大图。纳入徐州地铁 1、2、3、6 号线，按换乘站合并计 70 座车站。徐州东站的 1、6 号线站区分别估算接驳点，两线在站点统计中合并。

## 复现

使用 Python 3.12。先准备 Geofabrik 江苏 OSM PBF 数据，再安装依赖和运行脚本。

```sh
python -m pip install -r requirements.txt
python build.py --jiangsu /path/to/jiangsu-261122.osm.pbf --output xuzhou-metro-walk-1km.svg
```

本图采用 2026-11-22 21:20:48 UTC 的江苏路网快照。文件的 SHA-256 为 `627a393d0131fc685e9621774bf22be1408732c96e38dc93036334fff01c4845`。源码压缩包含静态成图所用的脚本。[从 Geofabrik 下载对应快照](https://download.geofabrik.de/asia/china/jiangsu-261122.osm.pbf)。使用不同日期的快照可能改变可达范围。

## 计算口径

站序和换乘信息按徐州地铁及高德运营线网核对。站点坐标和出入口来自 OpenStreetMap。算法优先按 OSM 站区关系分配出入口，然后按与运营车站的距离匹配剩余站口。每个站口就近连接到可步行道路，并将接驳距离计入 1,000 米预算。

以所有可用站口作为起点，在 WGS 84 / UTM 50N 中对步行图计算最短距离，保留 1,000 米内可达的路段和部分路段。珊瑚红色块使用 8 米网格估算可达路段附近的地表范围，考虑水面、建筑、围栏和限制通行区域。站口坐标缺失或无法接入步行图时，依据站位、已有步行道及少数关键站的官方出入口指南选择附近的估算接驳点。图中浅橙只显示由估算接驳点新增的覆盖。OSM 对站口、步道和门禁的标注完整度会影响局部结果。

- [徐州地铁运营信息](https://www.xzdtjt.com/3/index3.html)
- [徐州地铁的出入口指南](https://www.xzdtjt.com/1/52/station)
- [高德徐州地铁线网](https://maps.gaode.com/ssr/subway/xuzhou-3203)
- [Geofabrik 江苏路网](https://download.geofabrik.de/asia/china/jiangsu.html)
- [© OpenStreetMap contributors · ODbL](https://www.openstreetmap.org/copyright)
