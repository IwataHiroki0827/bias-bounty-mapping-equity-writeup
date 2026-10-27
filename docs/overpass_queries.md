# OpenStreetMap の実数照合に使った Overpass クエリ(Discovery、照合スクリプトの外)

エンドポイント: `https://overpass-api.de/api/interpreter`(POST、`data=` にクエリ)。API が混むと 504 / 429 / タイムアウトになるので、1件ずつ 20〜30 秒あけて投げた。
郡は `nist:fips_code`(州2桁+郡3桁)で指定する。

## バス停ノードの件数(2026-10-04、Harris・Bexar・Travis)

```
[out:json][timeout:300];
area["nist:fips_code"="48201"]->.a;
node["highway"="bus_stop"](area.a);
out count;
```

| 郡 | FIPS | OSM の bus_stop ノード | Overture の bus_stop(参考) |
|---|---|---:|---:|
| Harris(Houston) | 48201 | 680 | — |
| Bexar(San Antonio) | 48029 | 742 | 739 |
| Travis(Austin) | 48453 | 2,279 | 2,276 |

## バス停とバスのプラットフォーム(2026-10-03、Dallas・Nueces)

```
[out:json][timeout:120];
area["nist:fips_code"="48113"]->.a;
(node["highway"="bus_stop"](area.a); node["public_transport"="platform"]["bus"="yes"](area.a););
out count;
```

| 郡 | FIPS | OSM の件数 | Overture の bus_stop(参考) |
|---|---|---:|---:|
| Dallas | 48113 | 3,562 | 3,569 |
| Nueces(Corpus Christi) | 48355 | 1,261 | 1,261 |

OSM は毎日編集されるので、時期によって数件ずれる。
