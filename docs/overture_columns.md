# 配布データの Overture 属性の棚卸し(2026-10-15 夜)

目的: 上位との差 0.0048 を埋める新しい情報を、LB に使える配布データ(Overture 属性)の中から探す。
外部データは Bias Discovery 専用で、LB の提出には使わない。

## 方法

- スキーマ: reference の全 Overture レイヤー(roads・roads-unfiltered・pois・buildings・infrastructure・rail)の列をメタデータで確認した。
- 埋まり具合: TX の各レイヤーの先頭 5 万行だけを読んで確認した(軽い読み取り)。
  - roads と roads-unfiltered のクラス別件数は全地域で比べた(class 列だけ)。
- 要る偏差: 利得 MSE 2e-4 に要る相関の偏差 = √(2e-4 × 残差割合) / sd_y。sd_y = 0.0890(採点行)。
  - 残差割合(基準 25 本で説明できない分散の割合)は、まだ集計していない列について、近い既存特徴の値で見積もった(「類例」の列)。

| 残差割合 | 0.05 | 0.1 | 0.3 | 0.5 | 0.9 |
|---|---:|---:|---:|---:|---:|
| 要る偏差 | 0.036 | 0.050 | 0.087 | 0.112 | 0.151 |

## 事実

- **roads(配布)は roads-unfiltered をクラスで絞っただけ**で、幹線クラスは件数が全地域で完全に一致する。
  - 除かれたクラス: service・footway・track・path・unknown など。
  - 「フィルタで幹線が落ちて分子が減る」という機構は無い。
- 幹線(motorway〜secondary)の属性の埋まり具合(TX サンプル):
  - routes 60%、access_restrictions 85%、speed_limits 29%、road_flags 19%、road_surface 14%、subclass 13%(link)、width_rules 0%。
- tertiary の埋まり具合: speed_limits 13%、routes 23%。
- pois の属性(TX サンプル):
  - operating_status: 66% が値あり。そのうち permanently_closed は 1.5%。
  - basic_category 98%、brand 72%、websites 73%、phones 89%、confidence の平均 0.81。

## 棚卸し表

| レイヤー.列 | 未使用か | ギャップを説明しうる機構 | 類例(残差割合) | 要る偏差の見積もり | 判断 |
|---|---|---|---|---:|---|
| roads.speed_limits(tertiary 以下で ≥ 45 mph) | 未使用 | 速い tertiary・unclassified は機能上の collector で、参照の S1200 に入りうる(H5 の名前と別の手がかり) | t_named(0.05〜0.09) | 0.036〜0.048 | **集計する(H6)** |
| roads-unfiltered の class=unknown(名前が幹線の型) | 未使用 | 配布の roads から除かれた区間が参照には入っている | t_named | 約 0.04(km が幹線の 1% 未満なら棄却) | **集計する(H6、同じ集計で)** |
| roads.road_surface | 未使用 | 未舗装の幹線は参照の幹線に入らない | 低い埋まり(幹線 14%)で多くが 0 | 0.1 以上 | 見送り(埋まりが低く、未舗装の多くは TIGER でも local) |
| roads.width_rules | 未使用 | — | 埋まり 0% | — | 使えない |
| roads.access_restrictions・level_rules・road_flags・destinations | 未使用(destinations は Discovery で使用) | 区間の延長を変えない(通行規則・高架・行き先) | — | — | 見送り(機構なし) |
| roads.subclass=link | 使用済み(H3、t_k14_nolink) | 分子にランプが入る | 0.035 | 0.026 | 実施済み(残差 3.5%) |
| roads.sources.update_time | 使用済み(H4) | 取り込み時代の番号なし幹線 | — | — | 棄却済み(45 km) |
| pois.basic_category(家で営む業種) | 未使用 | CBP は従業員のいる事業所だけ。住宅サービス・不動産・美容などの places は CBP に対応が無く、分子だけを膨らませる | poi_lowconf_share(0.93) | 約 0.15 | **集計する(P2)**。ただし利得の上限は候補③と同程度(約 5e-5)の見込み |
| pois.operating_status(閉業) | 未使用 | 閉業の places が分子に入る | 同上 | 約 0.15 | P2 で数える(閉業は 1.5% と少なく、上限はさらに小さい) |
| pois.brand | 未使用 | チェーンは places に確実に載る。独立店の多い tract では places が CBP より少ない | bq_share(0.59) | 約 0.12 | P2 で数える |
| pois.websites・phones・addresses | 未使用 | 連絡先の無い places は質の低い記録(実在しない・重複) | poi_lowconf_share(0.93) | 約 0.15 | P2 で数える(confidence と重なる見込み) |
| pois.confidence | 使用済み(poi_lowconf_share) | 候補③ | 0.93 | 0.153 | 10/15 夜に検討済み(上限 4.5e-5) |
| buildings.height・num_floors・roof_*・facade_* | 未使用 | 建物の項の大きさ自体が小さい(建物ギャップの平均約 0.005) | — | — | 見送り(上限 MSE 5e-5、10/14 Fable) |
| infrastructure(バス停・空港など) | Discovery で使用 | 採点の4成分に入っていない | — | — | LB には見送り |
| rail | 未使用 | 参照の道路(S1100+S1200)に鉄道は入らない | — | — | 見送り |

## 結論と次の一手

- 大きく効きうるのは道路側(要る偏差 0.04 前後)だけ。事業所側は、仮説が真でも利得の上限が約 5e-5 にとどまる見込み。
  - 上位との差 0.0048 を一手で埋める列は、配布の Overture 属性の中には見当たらない。
- 集計の予定: `scripts/build_overture_extra.py`(H6 + P2 を1回で、全5地域。H5 と同程度の約2分・DuckDB 2GB)。受付の許可後に実行する。
- 事前登録(集計の後に特徴を作る。採否は従来どおり |実測(採点行) − null| > 0.015):

| 特徴(集計後に定義) | 真なら | 棄却の条件(プローブ前) |
|---|---|---|
| t_sp45 = ratio_gap(Overture 幹線, (ref + 速い tertiary 以下の km)×1.4) | 実測が null より上(速い tertiary は参照に数えられている) | 該当 km が地域の幹線 km の 1% 未満、または t_named と相関 0.98 超(同じ区間) |
| t_unk = 同じ形で、unknown の幹線名の km を足す | 同上 | 該当 km が 1% 未満 |
| home_share = 家で営む業種の places の割合 | 実測が null より上(事業所の分子が膨らんでいる) | なし。ただし枠の優先度は低い(10/19 以降の余り枠) |
