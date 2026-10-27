"""撤去された TIGER 幹線延長を、Overture の属性だけで近似する特徴(道路成分の推定用)。

採点の道路成分 = 1 - min(1, Overture 幹線延長 / TIGER S1100+S1200 延長)。公開議論(スレッド 35000)によると
TIGER 側の延長は次の2つで膨らむ。どちらも Overture から再現できる:
  1. 境界の二重計上: tract 境界は幹線に沿って引かれ、境界上の TIGER 線は隣り合う両 tract に入る。
     → tract の外側 d メートルの帯にある番号つき路線も、その tract の基準延長に足す。
  2. 重複路線: 複数の路線番号が同じ道路を共有すると、TIGER は番号ごとに同じ線を持つ。
     → 区間の routes に載る番号つき路線(I / US / 州道)の数を倍率にする。
番号つき路線 = network が US:I / US:US / US:<州> と、その付随(Business, Loop, Spur, Truck 等)。郡道は含めない。

出力: data/processed/tiger_proxy_<region>.parquet
  ov_hw_km          : tract 内の Overture 幹線延長(採点の分子)
  num_in_km         : tract 内の番号つき路線の延長(倍率なし)
  num_in_mult_km    : 同上、重複路線の倍率つき
  num_ring<d>_km    : 外側 d m の帯にある番号つき路線の延長(倍率つき)
使い方: python scripts/build_tiger_proxy.py [region ...] [--fm hw|all] [--nullnet]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
RINGS = (5, 15, 30)
NUM = r"US:(I|US|[A-Z]{2})(:(Business|Truck|Bypass|Loop|Spur|Alternate|Alt|Connector))?"
# テキサスの Farm/Ranch to Market 道路。TIGER は一部だけを S1200 にしている(未定義件数の照合から推定)。
# none: 含めない / hw: Overture でも幹線クラスの区間だけ含める / all: すべて含める
FM = r"US:[A-Z]{2}:(FM|RM)"
FM_MODE = "none"  # 既定。--fm hw|all で変種を別ファイルに出す


def m(g: str) -> str:
    return f"ST_Transform({g}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def build(con, region: str, fm: str = FM_MODE, nullnet: bool = False) -> None:
    """nullnet=True: routes の network が空でも ref(路線番号)がある幹線クラスの区間を番号つき路線に数える変種。
    route_networks.py の集計で、この種の区間が TX 約4,900km・AZ 約1,400km あり近似から漏れていた。"""
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE seg AS
        WITH r AS (
            SELECT {m('geometry')} AS g, class IN ('motorway','trunk','primary','secondary') AS hw,
                   list_distinct(list_transform(
                       list_filter(coalesce(routes, []), x -> regexp_full_match(coalesce(x.network, ''), '{NUM}')),
                       x -> x.network || '|' || coalesce(x.ref, ''))) AS nums,
                   list_distinct(list_transform(
                       list_filter(coalesce(routes, []), x -> regexp_full_match(coalesce(x.network, ''), '{FM}')),
                       x -> x.network || '|' || coalesce(x.ref, ''))) AS fms,
                   list_distinct(list_transform(
                       list_filter(coalesce(routes, []), x -> x.network IS NULL AND coalesce(x.ref, '') <> ''),
                       x -> x.ref)) AS nulls
            FROM {ref(region, 'overture-roads')}
        ), c AS (
            SELECT g, hw, len(nums) + CASE WHEN {str(nullnet).lower()} AND hw AND len(nums) = 0 THEN len(nulls) ELSE 0 END
                          + CASE '{fm}' WHEN 'all' THEN len(fms)
                                                       WHEN 'hw' THEN CASE WHEN hw THEN len(fms) ELSE 0 END
                                                       ELSE 0 END AS n_num
            FROM r
        )
        SELECT g, hw, n_num FROM c WHERE hw OR n_num > 0
    """)
    con.sql("CREATE OR REPLACE TEMP TABLE segnum AS SELECT g, n_num FROM seg WHERE n_num > 0")
    inside = con.sql("""
        SELECT tr.GEOID,
               sum(ST_Length(ST_Intersection(seg.g, tr.g))) FILTER (WHERE seg.hw) / 1000 AS ov_hw_km,
               sum(ST_Length(ST_Intersection(seg.g, tr.g))) FILTER (WHERE seg.n_num > 0) / 1000 AS num_in_km,
               sum(ST_Length(ST_Intersection(seg.g, tr.g)) * seg.n_num) FILTER (WHERE seg.n_num > 0) / 1000 AS num_in_mult_km
        FROM seg JOIN tr ON ST_Intersects(seg.g, tr.g) GROUP BY 1
    """).df().set_index("GEOID")
    parts = [inside]
    for d in RINGS:
        con.sql(f"CREATE OR REPLACE TEMP TABLE ring AS SELECT GEOID, ST_Difference(ST_Buffer(g, {d}), g) AS g FROM tr")
        # 帯の中の区間のうち、境界に沿って走るもの(長さが帯の幅の 3 倍以上)だけを数えた版も出す。
        # 境界を直交してまたぐ道路の端(1 回あたり最大 d m)を拾わないため
        parts.append(con.sql(f"""
            WITH x AS (
                SELECT ring.GEOID, s.n_num, ST_Length(ST_Intersection(s.g, ring.g)) AS l
                FROM segnum s JOIN ring ON ST_Intersects(s.g, ring.g)
            )
            SELECT GEOID, sum(l * n_num) / 1000 AS num_ring{d}_km,
                   sum(l * n_num) FILTER (WHERE l >= {3 * d}) / 1000 AS num_ringpar{d}_km
            FROM x GROUP BY 1
        """).df().set_index("GEOID"))
    df = parts[0].join(parts[1:], how="outer").reset_index()
    suffix = ("" if fm == "none" else f"_fm{fm}") + ("_nn" if nullnet else "")
    df.to_parquet(OUT / f"tiger_proxy_{region}{suffix}.parquet", index=False)
    print(f"[{region}] rows={len(df)} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    args = sys.argv[1:]
    fm = FM_MODE
    if "--fm" in args:
        i = args.index("--fm")
        fm = args[i + 1]
        del args[i:i + 2]
    nullnet = "--nullnet" in args
    args = [a for a in args if a != "--nullnet"]
    con = connect()
    for region in args or REGIONS:
        build(con, region, fm, nullnet)


if __name__ == "__main__":
    main()
