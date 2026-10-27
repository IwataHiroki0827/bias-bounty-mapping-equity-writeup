"""tract ごとの特徴テーブルを組み立て、提出候補となる特徴列(0〜1)を作る。

入力(data/processed/): features_<region>, routes_<region>, boundary_<region>, features_all(strata 付き)
すべて Overture・ACS・strata のみから作る。撤去された参照データは使わない。
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from src.env import ROOT
from src.remote import REGIONS

P = ROOT / "data" / "processed"
BIN_EDGES = [0.02, 0.06, 0.12, 0.20]  # 予測 ŷ のビンの境界(ybin1〜4、scripts/yhat_bins.py)


def load() -> pd.DataFrame:
    base = pd.read_parquet(P / "features_all.parquet")
    rt = pd.concat([pd.read_parquet(P / f"routes_{r}.parquet") for r in REGIONS])
    bd = pd.concat([pd.read_parquet(P / f"boundary_{r}.parquet") for r in REGIONS])
    tg = pd.concat([pd.read_parquet(P / f"tiger_proxy_{r}.parquet") for r in REGIONS])
    tg = tg.rename(columns={c: f"tg_{c}" for c in tg.columns if c != "GEOID"})
    # 南TXの FM 変種(幹線クラスの FM を番号つき路線に含める)。他地域は既定と同じ値
    fm_path = P / "tiger_proxy_south-central-tx_fmhw.parquet"
    if fm_path.exists():
        fm = pd.read_parquet(fm_path)
        tg = tg.merge(fm.rename(columns={c: f"tgfm_{c}" for c in fm.columns if c != "GEOID"}), on="GEOID", how="left")
    # network が空でも ref がある幹線区間を数えた変種(build_tiger_proxy.py --nullnet)。全地域そろっているときだけ
    nn_paths = [P / f"tiger_proxy_{r}_nn.parquet" for r in REGIONS]
    if all(p.exists() for p in nn_paths):
        nn = pd.concat([pd.read_parquet(p) for p in nn_paths])
        tg = tg.merge(nn.rename(columns={c: f"tgnn_{c}" for c in nn.columns if c != "GEOID"}), on="GEOID", how="left")
    pp = pd.concat([pd.read_parquet(P / f"poi_{r}.parquet") for r in REGIONS])
    pp = pp.rename(columns={c: f"pp_{c}" for c in pp.columns if c != "GEOID"})
    d = (base.merge(rt, on="GEOID", how="left").merge(bd, on="GEOID", how="left")
             .merge(tg, on="GEOID", how="left").merge(pp, on="GEOID", how="left"))
    num = d.select_dtypes("number").columns
    fill0 = [c for c in num if c.startswith(("rt_", "hw_", "tg_", "pp_", "road_", "bldg_", "poi_n", "poi_fire", "poi_ems",
                                             "poi_school", "poi_hospital"))]
    d[fill0] = d[fill0].fillna(0)
    # 道路の取りこぼし仮説 H1・H3 の集計(scripts/build_road_hyp.py)。全地域そろっているときだけ
    hyp_paths = [P / f"road_hyp_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in hyp_paths):
        hyp = pd.concat([pd.read_parquet(p) for p in hyp_paths])
        d = d.merge(hyp, on="GEOID", how="left")
        d[["h1_pair_km", "h3_link_km"]] = d[["h1_pair_km", "h3_link_km"]].fillna(0)
    # H5: 名前で見る幹線(scripts/build_road_named.py)。全地域そろっているときだけ
    nm_paths = [P / f"road_named_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in nm_paths):
        nm = pd.concat([pd.read_parquet(p) for p in nm_paths])
        d = d.merge(nm, on="GEOID", how="left")
        nm_cols = [c for c in nm.columns if c.startswith("nm_")]
        d[nm_cols] = d[nm_cols].fillna(0)
    # H6・P2: 速い tertiary 以下・unknown の幹線名・places の業種/閉業/チェーン/連絡先(scripts/build_overture_extra.py)
    ox_paths = [P / f"ov_extra_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in ox_paths):
        ox = pd.concat([pd.read_parquet(p) for p in ox_paths])
        d = d.merge(ox, on="GEOID", how="left")
        ox_cols = [c for c in ox.columns if c != "GEOID"]
        d[ox_cols] = d[ox_cols].fillna(0)
    # tertiary の制限速度の埋まり(scripts/build_speed_fill.py)。sp45_imp の材料
    sf_paths = [P / f"ov_speed_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in sf_paths):
        sf = pd.concat([pd.read_parquet(p) for p in sf_paths])
        d = d.merge(sf, on="GEOID", how="left")
        d[["ter_km_all", "ter_km_sp", "ter_km_sp45"]] = d[["ter_km_all", "ter_km_sp", "ter_km_sp45"]].fillna(0)
    # USDA RUCA 2020(strata の配布物)。取得: scripts/fetch_ruca.py
    ruca_path = P / "ruca_all.parquet"
    if ruca_path.exists():
        ru = pd.read_parquet(ruca_path, columns=["GEOID", "ruca_primary", "ruca_pop_density", "ruca_land_area_sqmi"])
        d = d.merge(ru.drop_duplicates("GEOID"), on="GEOID", how="left")
    # 配布 strata 表の追加列(陸域面積・都市人口の割合・郡の都市化区分)。取得: scripts/fetch_strata_extra.py
    sx_path = P / "strata_extra.parquet"
    if sx_path.exists():
        d = d.merge(pd.read_parquet(sx_path), on="GEOID", how="left")
    # Overture places の供給元別の件数(scripts/build_place_sources.py)。全地域そろっているときだけ
    ps_paths = [P / f"place_sources_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in ps_paths):
        ps = pd.concat([pd.read_parquet(p) for p in ps_paths])
        d = d.merge(ps, on="GEOID", how="left")
        d[[c for c in ps.columns if c != "GEOID"]] = d[[c for c in ps.columns if c != "GEOID"]].fillna(0)
    # Overture buildings の供給元別の面積・大きさ(scripts/build_bldg_sources.py)。全地域そろっているときだけ
    bs_paths = [P / f"bldg_sources_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in bs_paths):
        d = d.merge(pd.concat([pd.read_parquet(p) for p in bs_paths]), on="GEOID", how="left")
    # F1: Overture buildings の class / names で数えた消防・学校・EMS の建物(scripts/build_bldg_facility.py)
    bf_paths = [P / f"bldg_facility_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in bf_paths):
        bf = pd.concat([pd.read_parquet(p) for p in bf_paths])
        d = d.merge(bf, on="GEOID", how="left")
        d[[c for c in bf.columns if c != "GEOID"]] = d[[c for c in bf.columns if c != "GEOID"]].fillna(0)
    # F2・F4: 境界の外側・内側の消防の点と categories.alternate の施設(scripts/build_facility_near.py)
    fn_paths = [P / f"facnear_{r}.parquet" for r in REGIONS]
    if all(p.exists() for p in fn_paths):
        fn = pd.concat([pd.read_parquet(p) for p in fn_paths])
        d = d.merge(fn, on="GEOID", how="left")
        d[[c for c in fn.columns if c != "GEOID"]] = d[[c for c in fn.columns if c != "GEOID"]].fillna(0)
    # 10/24: 採点の偏りの指標に当たる strata の列(scripts/build_strata_hazard.py)
    hz = P / "strata_hazard.parquet"
    if hz.exists():
        h = pd.read_parquet(hz).drop_duplicates("GEOID")
        d = d.merge(h[[c for c in h.columns if c == "GEOID" or c not in d]], on="GEOID", how="left")
    return d


def ratio_gap(obs: pd.Series, ref: pd.Series) -> pd.Series:
    """採点式と同じ形 1 - min(1, obs/ref)。ref<=0 は未定義として NaN。"""
    r = obs / ref.where(ref > 0)
    return 1 - r.clip(upper=1)


def candidates(d: pd.DataFrame) -> dict[str, pd.Series]:
    """提出で相関を測る候補特徴。値は 0〜1、未定義は 0 で埋める。"""
    pop = d["pop_total"].fillna(0)
    c: dict[str, pd.Series] = {}
    for dist in (10, 25, 50, 100):
        c[f"t_bound{dist}"] = ratio_gap(d["hw_in_km"], d[f"hw_buf{dist}_km"]).fillna(0)
    # TIGER 幹線延長の近似 = 番号つき路線(重複路線は倍率)+ 境界の外側 d m の帯(二重計上)。スレッド 35000 の機構
    for ring in (5, 15, 30):
        ref = d["tg_num_in_mult_km"] + d[f"tg_num_ring{ring}_km"]
        c[f"t_tiger{ring}"] = ratio_gap(d["tg_ov_hw_km"], ref).fillna(0)
    for ring in (15, 30):
        ref = d["tg_num_in_mult_km"] + d[f"tg_num_ringpar{ring}_km"]
        c[f"t_tigerpar{ring}"] = ratio_gap(d["tg_ov_hw_km"], ref).fillna(0)
    # 地域ダミーと、道路推定×地域の交互作用(4 本をプローブすれば 5 本目は和の制約から決まる)
    for r in REGIONS:
        m = (d["region"] == r).astype(float)
        c[f"reg_{r}"] = m
        c[f"t15x_{r}"] = c["t_tiger15"] * m
    if "tgfm_num_in_mult_km" in d:
        tx = d["region"] == "south-central-tx"
        ref = (d["tgfm_num_in_mult_km"] + d["tgfm_num_ring15_km"]).where(tx, d["tg_num_in_mult_km"] + d["tg_num_ring15_km"])
        ov = d["tgfm_ov_hw_km"].where(tx, d["tg_ov_hw_km"])
        c["t_tiger15_fm"] = ratio_gap(ov.fillna(0), ref.fillna(0)).fillna(0)
    c["comp_v1"] = composite_v1(d)
    # 基準延長の倍率 k(番号つき路線の近似が TIGER の一部を取りこぼす分)。k は格子で置き、LB の相関だけで選ぶ。
    # 他参加者が撤去済み参照データから出した公開集計(地域平均など)で k を決めない(規約、2026-10-03 ユーザー決定)
    ref = d["tg_num_in_mult_km"] + d["tg_num_ring15_km"]
    for kk in (12, 14, 16, 20):
        c[f"t_k{kk}"] = ratio_gap(d["tg_ov_hw_km"], ref * kk / 10).fillna(0)
    # 10/14: 地域別の k を min(1,·) の中で使う版(Fable の仮説1)。k は期待値モデル(scripts/expected_model.py)を
    # 当方のプローブの共分散に一致させて解いた値(OK 1.45 / AZ 1.05 / CA 1.36 / TX 1.21、WA は 1.4)
    k_reg = d["region"].map({"eastern-ok": 1.45, "maricopa-az": 1.05, "northern-ca": 1.36,
                             "south-central-tx": 1.21}).fillna(1.4)
    c["t_kreg"] = ratio_gap(d["tg_ov_hw_km"], ref * k_reg).fillna(0)
    # 2026-10-04 の LB 格子で k=1.4 を選んだ(相関 k=1.0 0.610 / 1.4 0.684 / 2.0 0.683)
    c["comp_k14"] = composite_v1(d, k=1.4)
    # 仮説 H2(docs/road_hypotheses.md): 番号の無い幹線(primary/secondary 等)の一部 b を基準に足し、倍率を外す。
    # 未定義の判定は元の基準で行う。b=0.5 で t_k14 との相関 0.94(別の1本として測る価値がある)
    # 道路の取りこぼし仮説 H1・H3(docs/road_hypotheses.md、scripts/build_road_hyp.py の集計)
    if "h3_link_km" in d:
        # H3: 分子の Overture 幹線延長からランプ(motorway/trunk の link)を除く。TIGER のランプは S1630 で基準に入らない
        c["t_k14_nolink"] = ratio_gap((d["tg_ov_hw_km"] - d["h3_link_km"]).clip(lower=0), ref * 1.4).fillna(0)
        # H1: 番号つき本線と 60m 以内に並走する番号なし本線(上下線の片側だけに routes)を基準に足す
        c["t_k14_h1"] = ratio_gap(d["tg_ov_hw_km"], (ref + d["h1_pair_km"]) * 1.4).fillna(0)
    # 道路成分の未定義(基準 0)の扱い。採点は定義された成分だけの平均なので、未定義かどうかが重みを変える
    c["road_undef"] = (ref <= 0).astype(float)
    # 「未定義 / 定義で比≥1 / 定義で gap>0」の3状態の段差(Fable 分析 10/4: 既存で説明できない残差 13.5%)
    c["t_pos"] = ((ref > 0) & (c["t_k14"] > 0)).astype(float)
    # 10/10: 道路推定(k=1.4)× 地域。合成の傾きは地域で 0.6〜1.1 と違った(c1x)。道路だけの傾きも地域で違うかを測る
    for r in REGIONS:
        c[f"tk14x_{r}"] = c["t_k14"] * (d["region"] == r)
        # 10/12: 道路の効きが地域で違った(TX 小・OK 大)。道路の3状態(未定義・ギャップあり)も地域で効きが違うかを測る
        c[f"undefx_{r}"] = c["road_undef"] * (d["region"] == r)
        c[f"tposx_{r}"] = c["t_pos"] * (d["region"] == r)
    # 10/10: 道路が未定義の tract では、施設の重みが 1/3 → 1/2 に上がる(採点は定義された成分だけの平均)。
    # 合成の傾きを、道路が未定義の tract だけ別に取る
    c["comp_undef"] = c["comp_k14"] * c["road_undef"]
    # 10/10: 道路ギャップの曲がり(比の推定は 0〜1 で頭打ち。線形では大きい側と小さい側を同じ傾きで扱ってしまう)
    c["t_k14_sq"] = c["t_k14"] ** 2
    # Overture 幹線が基準を大きく超える tract は基準が過小(番号なし幹線が多い)と考えられる。超過の大きさ
    r_over = d["tg_ov_hw_km"] / (ref * 1.4).where(ref > 0)
    c["ratio_over"] = (1 - 1 / r_over.clip(lower=1)).fillna(0)
    # TX: 番号つき路線が無く未定義と推定した tract のうち、FM(幹線クラス)路線がある tract だけで道路ギャップを立てる。
    # 全 tract に FM を足した t_tiger15_fm は過大で悪化したので、対象を「基準 0」の tract に限る(Fable 分析 10/4)
    if "tgfm_num_in_mult_km" in d:
        fmref = d["tgfm_num_in_mult_km"].fillna(0) + d["tgfm_num_ring15_km"].fillna(0)
        fm_only = (ref <= 0) & (fmref > 0)
        c["t_fm_only"] = ratio_gap(d["tg_ov_hw_km"], fmref * 1.4).where(fm_only, 0.0).fillna(0)
    nonnum = (d["tg_ov_hw_km"] - d["tg_num_in_km"]).clip(lower=0)
    for b, name in ((0.5, "t_h2b05"), (1.0, "t_h2b10")):
        c[name] = ratio_gap(d["tg_ov_hw_km"], (ref + b * nonnum).where(ref > 0)).fillna(0)
    # Fable 分析(10/6)の 10/8 候補。予測と採否は docs/probe_plan.md に事前登録
    c["t_cty10"] = ratio_gap(d["tg_ov_hw_km"], (ref + d["rt_county_km"].fillna(0)) * 1.4).fillna(0)  # 郡道番号は S1200 に入る
    c["unnum_share"] = (nonnum / d["tg_ov_hw_km"].where(d["tg_ov_hw_km"] > 0)).fillna(0)  # 番号なし幹線は分子だけを膨らませる
    c["t_ter05"] = ratio_gap(d["tg_ov_hw_km"], (ref + 0.5 * d["road_tertiary_km"].fillna(0)) * 1.4).fillna(0)  # S1200 ⊃ tertiary
    # Fable 分析(10/10)の候補: 残る誤差は「基準延長の取りこぼし(k=1.4 で水準だけ吸収した約4割)がどの tract にあるか」
    ter = d["road_tertiary_km"].fillna(0)
    hw = d["road_hw_km"].fillna(0)
    local = (d["road_all_km"].fillna(0) - hw - ter).clip(lower=0)
    c["t_ter10_k14"] = ratio_gap(d["tg_ov_hw_km"], (ref + 1.0 * ter) * 1.4).fillna(0)  # t_ter05 の +0.046 の延長
    c["t_loc_k10"] = ratio_gap(d["tg_ov_hw_km"], ref + 0.081 * local).fillna(0)  # 取りこぼしを住宅街の道路で埋める形
    c["ter_share"] = (ter / (hw + ter).where(hw + ter > 0)).fillna(0)
    c["tk14_x_tershare"] = c["t_k14"] * c["ter_share"]  # k の膨らませが正しいのは tertiary の多い tract だけ(乗法)
    c["tk14_x_unnum"] = c["t_k14"] * c["unnum_share"]  # 番号なし幹線が多い tract では道路の傾きが小さい
    if "tgnn_num_in_mult_km" in d:
        ref_nn = d["tgnn_num_in_mult_km"].fillna(0) + d["tgnn_num_ring15_km"].fillna(0)
        c["t_k14nn"] = ratio_gap(d["tgnn_ov_hw_km"].fillna(0), ref_nn * 1.4).fillna(0)
    # 10/15 Fable の案②: 参照の道路分類は郡単位の供給元で決まる。郡の合計で Overture 幹線と番号つき近似が一致する k を
    # min(1,·) の中で使う(郡の比は 0.76〜2.02 とばらつく)。郡の定数そのものは出さず、k としてだけ使う
    cty = d["STATEFP"].astype(str) + d["COUNTYFP"].astype(str)
    g = pd.DataFrame({"cty": cty, "ov": d["tg_ov_hw_km"], "ref": ref,
                      "unnum": nonnum}).groupby("cty").sum()
    k_all = g["ov"].sum() / g["ref"].sum()
    k_cty = cty.map((g["ov"] / g["ref"].where(g["ref"] > 0)).fillna(k_all))
    c["t_kcty"] = ratio_gap(d["tg_ov_hw_km"], ref * k_cty).fillna(0)
    c["tk14_x_ctyunnum"] = c["t_k14"] * cty.map((g["unnum"] / g["ov"].where(g["ov"] > 0)).fillna(0))
    # 10/15 H5(docs/road_hypotheses.md): 名前は幹線の型なのに Overture では tertiary 以下の区間を参照の近似に足す。
    # 郡道の名前で residential/unclassified の区間(TX 76,490 km)は TIGER では主に S1400(local)なので入れない
    if "nm_fm_ter_km" in d:
        named = d[["nm_fm_ter_km", "nm_fm_loc_km", "nm_st_ter_km", "nm_st_loc_km", "nm_cty_ter_km"]].sum(axis=1)
        c["t_named"] = ratio_gap(d["tg_ov_hw_km"], (ref + named) * 1.4).fillna(0)
        c["named_share"] = (named / (named + d["tg_ov_hw_km"]).where(named + d["tg_ov_hw_km"] > 0)).fillna(0)
        c["t_named_fm"] = ratio_gap(d["tg_ov_hw_km"], (ref + d["nm_fm_ter_km"] + d["nm_fm_loc_km"]) * 1.4).fillna(0)
        # 10/15 夜: t_named(_fm) が当たったときの後続。合成値の道路項の基準に同じ km を足す(未定義の扱いも採点式どおり)
        c["comp_named"] = composite_v1(d, k=1.4, extra_km=named)
        c["comp_named_fm"] = composite_v1(d, k=1.4, extra_km=d["nm_fm_ter_km"] + d["nm_fm_loc_km"])
    # 10/15 夜 H6(docs/overture_columns.md): 制限速度 45 mph 以上の tertiary は機能上の collector(S1200 の候補)。
    # residential/unclassified の速い区間は OK の区画線道路の既定速度が大半(TIGER では local)なので別の特徴にする
    if "sp45_ter_km" in d:
        c["t_sp45"] = ratio_gap(d["tg_ov_hw_km"], (ref + d["sp45_ter_km"]) * 1.4).fillna(0)
        c["t_sp45_all"] = ratio_gap(d["tg_ov_hw_km"], (ref + d["sp45_ter_km"] + d["sp45_loc_km"]) * 1.4).fillna(0)
        c["comp_sp45"] = composite_v1(d, k=1.4, extra_km=d["sp45_ter_km"])  # t_sp45 が当たったときの後続(合成値の中)
    if "ter_km_sp" in d:
        # 制限速度の無い tertiary を、地域の「埋まった区間のうち ≥45 の割合」で補う(10/16 事前登録)
        g = d.groupby("region")[["ter_km_sp", "ter_km_sp45"]].transform("sum")
        p45 = g["ter_km_sp45"] / g["ter_km_sp"].where(g["ter_km_sp"] > 0)
        imp = d["ter_km_sp45"] + (d["ter_km_all"] - d["ter_km_sp"]) * p45.fillna(0)
        c["t_sp45_imp"] = ratio_gap(d["tg_ov_hw_km"], (ref + imp) * 1.4).fillna(0)
        c["comp_sp45_imp"] = composite_v1(d, k=1.4, extra_km=imp)
        # P2: 事業所の分子を膨らませうる places の割合(CBP に対応の無い家で営む業種・閉業・連絡先なし)とチェーンの割合
        n = d["pp_poi_all_n"].where(d["pp_poi_all_n"] > 0)
        for k in ("home", "closed", "brand", "nocontact"):
            c[f"{k}_share"] = (d[f"pl_{k}_n"] / n).clip(upper=1).fillna(0)
    # 道路成分は地域間で比較できない(README)。comp_v1 × 地域の交互作用で地域別の傾きを測る(4本で5地域が決まる)
    for r in REGIONS:
        c[f"c1x_{r}"] = c["comp_v1"] * (d["region"] == r)
    # 都市の規模(RUCA)。小都市の中心部は Urban 区分でも被覆が薄い(公開スレッド 34993 の機構)
    if "ruca_primary" in d:
        rp = d["ruca_primary"]
        c["small_core"] = rp.isin([4, 7]).astype(float)
        # 10/11: small_core が null から +0.061 ずれた → 都市化の区分そのものに、モデルが拾えていない情報がある。区分ごとの 0/1
        c["ruca_core"] = (rp == 1).astype(float)  # 大都市の中心
        c["ruca_metro_comm"] = rp.isin([2, 3]).astype(float)  # 大都市への通勤圏
        c["ruca_micro_comm"] = rp.isin([5, 6]).astype(float)  # 小都市への通勤圏
        c["ruca_small_town"] = rp.isin([8, 9]).astype(float)  # 町とその通勤圏
        c["ruca_rural10"] = (rp == 10).astype(float)  # 農村
        # 10/14: ruca_core(−)と tk14_x_tershare(+)がともに当たり → 大都市の中心では道路ギャップの効きも小さいか
        c["tk14_x_core"] = c["t_k14"] * c["ruca_core"]
    if "nchs_2013" in d:
        # 郡の都市化区分(NCHS 2013: 1 大都市の中心郡 … 6 非都市圏)
        for k in range(1, 7):
            c[f"nchs{k}"] = (d["nchs_2013"] == k).astype(float)
        # 陸域面積(対数を 0〜1 に)。広い tract ほど基準側の道路が多い
        la = np.log1p(d["ALAND"].fillna(0) / 1e6)
        c["log_aland"] = (la / la.max()).fillna(0)
        c["tk14_x_aland"] = c["t_k14"] * c["log_aland"]
        c["nonmetro"] = (rp >= 4).astype(float)
        c["rural_ur"] = (d["ur_class"] == "Rural").astype(float)
        c["rur_x_tx"] = c["rural_ur"] * (d["region"] == "south-central-tx")
        c["tk14_rural"] = c["t_k14"] * c["rural_ur"]  # 道路の傾きの都市/農村分割(Fable 10/6)
        # Fable 10/7: ur_class=Rural の半分近くは都市圏の縁(RUCA 1〜3)。深い農村(RUCA 7 以上)だけを分ける
        c["rural_deep"] = (c["rural_ur"].astype(bool) & (rp >= 7)).astype(float)
        # Fable 10/7: 広い農村 tract は基準側に複数の消防署があり、Overture が1署でも消防ギャップが残りうる
        area = d["ruca_land_area_sqmi"]
        big = area >= area[c["rural_ur"].astype(bool)].quantile(0.75)  # 農村の中の面積上位四分位
        c["rural_fire_big"] = (c["rural_ur"].astype(bool) & (d["pp_fire_cat_n"] > 0) & big).astype(float)
    # 消防: 名前でもカテゴリでも消防署が見つからない tract。基準側に消防署があれば消防=1 になる層。
    # 農村・部族地域で多いと考えられるが、重みは公開集計でなく LB の相関で決める
    fire0 = (d["pp_fire_cat_n"] == 0) & (d["pp_fire_misfiled_n"] == 0)
    c["fire0_rural"] = (fire0 & (d["ur_class"] == "Rural")).astype(float)
    # Fable 10/14: 消防なし ∧ 道路未定義。道路が未定義だと施設の重みが 1/3 → 1/2 に上がり、合成が 0.25〜0.5 になりうる
    c["fire0_undef"] = (fire0 & c["road_undef"].astype(bool)).astype(float)
    c["fire0_tribal"] = (fire0 & d["tribal_any"].fillna(False).astype(bool)).astype(float)
    # 10/23: 基準が残した偏りを Discovery の証拠として測る切り口(社会的脆弱性の両端・部族の土地)
    c["tribal_any"] = d["tribal_any"].fillna(False).astype(bool).astype(float)
    if "svi_overall" in d:
        c["svi_high"] = (d["svi_overall"] >= 0.75).astype(float)
        c["svi_low"] = (d["svi_overall"] <= 0.25).astype(float)
    # 10/24: 採点の偏りの指標(山火事・夏の暑熱・夏の干ばつ・CVI)の上位 25%、と危険 × 脆弱の交差
    if "usfs_WHP_mean" in d:
        hi = {k: d[k] >= d[k].quantile(0.75) for k in ["usfs_WHP_mean", "epht_heat_days_summer", "usdm_summer_dsci", "cvi_overall"]}
        c["wildfire_high"] = hi["usfs_WHP_mean"].astype(float)
        c["heat_high"] = hi["epht_heat_days_summer"].astype(float)
        c["drought_high"] = hi["usdm_summer_dsci"].astype(float)
        c["cvi_high"] = hi["cvi_overall"].astype(float)
        hazard = hi["usfs_WHP_mean"] | hi["epht_heat_days_summer"] | hi["usdm_summer_dsci"]
        c["hazard_x_svi"] = (hazard & (d["svi_overall"] >= 0.75)).astype(float)
        # 10/25: 10/24 の裏側(下位 25%)・冬の干ばつ・都市/農村 × 高 SVI の交差
        c["wildfire_low"] = (d["usfs_WHP_mean"] <= d["usfs_WHP_mean"].quantile(0.25)).astype(float)
        c["cvi_low"] = (d["cvi_overall"] <= d["cvi_overall"].quantile(0.25)).astype(float)
        c["drought_w_high"] = (d["usdm_winter_dsci"] >= d["usdm_winter_dsci"].quantile(0.75)).astype(float)
        rur = d["ur_class"] == "Rural"
        c["rural_x_svi"] = (rur & (d["svi_overall"] >= 0.75)).astype(float)
        c["urban_x_svi"] = (~rur & (d["svi_overall"] >= 0.75)).astype(float)
    # 消防署カテゴリ 0 だが fire_protection_service の施設がある(採点カテゴリ外の実在消防。スレッド 34925 と同型)
    c["fire0_prot"] = ((d["pp_fire_cat_n"] == 0) & (d["pp_fire_prot_n"] > 0)).astype(float)
    # Fable 分析(10/5)の仮説。採点式のうち、まだ測っていない成分(EMS・building・CBP 半分)と、未定義による重みの変化
    # E1: 消防署はあるが EMS が無い(EMS 項 = 1 になりやすい)
    c["ems0_fire1"] = ((d["pp_ems_cat_n"] == 0) & (d["pp_ems_misfiled_n"] == 0) & (d["pp_fire_cat_n"] > 0)).astype(float)
    # B1: Overture の建物のうち OSM 由来の割合(OSM は離れ・車庫を描かず併合しがち → Overture 棟 < MS 棟)
    c["b_osm_share"] = (d["bldg_osm_n"] / d["bldg_n"].where(d["bldg_n"] > 0)).fillna(0)
    # 10/14 外の調査: 建物成分(Overture 棟 / MS 棟)の代理を配布 ACS の住戸数で作る。住戸より Overture の棟が
    # 少ない tract は、MS が拾う戸建て・離れを Overture(OSM の併合)が欠いている可能性がある
    hu = d["housing_units"].astype(float)
    c["bldg_short_hu"] = ratio_gap(d["bldg_n"], hu).fillna(0)
    c["bldg_short_hu06"] = ratio_gap(d["bldg_n"], hu * 0.6).fillna(0)
    c["b_ms_share"] = (d["bldg_ms_n"] / d["bldg_n"].where(d["bldg_n"] > 0)).fillna(0)
    # Overture の統合は OSM → Esri → Google 高 → MS の優先順で、MS は上位と交差しない棟だけが入る(公式 buildings ガイド)。
    # Overture 棟 < MS 棟になるのは、上位(OSM 等)の大きな1ポリゴンが MS の複数棟を覆う tract → 上位由来の割合 × 棟の不足
    nonms = 1 - c["b_ms_share"]
    c["b_nonms_x_short"] = nonms * c["bldg_short_hu"]
    mean_area = d["bldg_area_m2"] / d["bldg_n"].where(d["bldg_n"] > 0)
    big = np.log(mean_area.clip(lower=1)).fillna(0)
    c["b_nonms_x_bigarea"] = nonms * ((big - big.quantile(0.5)).clip(lower=0) / max(big.max() - big.quantile(0.5), 1e-9))
    if "bs_up_area" in d:
        # 上位(OSM 等)由来の棟の中央面積が、同じ tract の MS 由来の棟の何倍か(大きいほど併合して描いている)
        up_n = (d["bldg_n"] - d["bldg_ms_n"]).astype(float)
        ratio = (d["bs_up_med_area"] / d["bs_ms_med_area"]).astype(float)
        lr = np.log(ratio.clip(lower=1)).fillna(0)
        c["b_merge"] = (nonms * (lr / max(float(lr.quantile(0.99)), 1e-9))).clip(0, 1)
        # 上位由来の大きな棟(400m² 以上)の割合 × 上位由来の割合
        c["b_upbig"] = (d["bs_up_big400_n"] / up_n.where(up_n > 0)).fillna(0) * nonms
        # 小さな棟(60m² 未満: 物置・離れ)は MS だけが拾う。上位由来の棟に小さな棟が少ないほど、MS 側に置き換えられない棟がある
        small_up = (d["bs_up_small_n"] / up_n.where(up_n > 0)).fillna(0)
        small_ms = (d["bs_ms_small_n"] / d["bldg_ms_n"].where(d["bldg_ms_n"] > 0)).astype(float)
        c["b_nosmall"] = (nonms * (small_ms.fillna(small_ms.median()) - small_up).clip(lower=0)).fillna(0)
    # 事業所半分(Overture places / CBP 事業所)の代理の分母を住戸数に替えた版
    c["poi_short_hu"] = ratio_gap(d["poi_n"], hu / 6).fillna(0)
    c["comp_k14_fireprot"] = composite_v1(d, k=1.4, fire_q=(d["pp_fire_prot_n"] > 0).astype(float))
    c["fire_none"] = (d["poi_fire_n"] == 0).astype(float)
    # 実在の消防署があるのに採点カテゴリでは 0 件(スレッド 34925 の機構)
    c["fire_misfiled"] = ((d["pp_fire_cat_n"] == 0) & (d["pp_fire_misfiled_n"] > 0)).astype(float)
    c["school_short"] = ratio_gap(d["poi_school_n"], pop / 2500).fillna(0)
    c["poi_short"] = ratio_gap(d["poi_n"], pop / 15).fillna(0)
    # 10/14 外の調査(スレッド 35325 の考え方): 事業所の分母 = 米国の住民1人あたり事業所数 0.0243 × 人口
    # Fable 10/14: 信頼度の低い places(閉店・重複)は CBP 半分の実効の分子を小さくする
    c["poi_lowconf_share"] = (d["pp_poi_lowconf_n"] / d["pp_poi_all_n"].where(d["pp_poi_all_n"] > 0)).fillna(0)
    c["poi_short41"] =ratio_gap(d["poi_n"], pop * 0.0243).fillna(0)
    # 10/14 P4: CBP は tract 単位で公表されないので、郡・ZIP の事業所数を人口などで tract に按分したものと推測。
    # そうなら住宅地の tract にも郡並みの事業所が割り当てられ、places の少ない住宅地でギャップが出る
    # → 分母 = 人口 × 郡の places / 人口(郡の平均並みなら 0、住宅地ほど大きい)
    cty = d["STATEFP"].astype(str) + d["COUNTYFP"].astype(str)
    rate = d.groupby(cty)["poi_n"].transform("sum") / pop.groupby(cty).transform("sum").where(lambda s: s > 0)
    c["poi_short_cty"] = ratio_gap(d["poi_n"], pop * rate).fillna(0)
    if "ps_n_BrightQuery" in d:
        bq = d["ps_n_BrightQuery"].astype(float)
        c["bq_share"] = (bq / d["poi_n"].where(d["poi_n"] > 0)).fillna(0)
        rate_bq = bq.groupby(cty).transform("sum") / pop.groupby(cty).transform("sum").where(lambda s: s > 0)
        c["bq_short_cty"] = ratio_gap(bq, pop * rate_bq).fillna(0)
        meta = d["ps_n_meta"].astype(float)
        c["meta_share"] = (meta / d["poi_n"].where(d["poi_n"] > 0)).fillna(0)
    # 消防署が1件以上ある tract でも、参照側に追加の署 K ~ Poisson(u·λ) があれば消防項は K/(O+K)。
    # λ は Overture の消防署数を人口・面積・地域で回帰した期待件数(配布データだけ)。u = 0.45 は 35325 の値
    if "ALAND" in d:
        from sklearn.linear_model import PoissonRegressor
        Xf = pd.DataFrame({"lp": np.log1p(pop), "la": np.log1p(d["ALAND"].fillna(0) / 1e6),
                           "rur": (d["ur_class"] == "Rural").astype(float)})
        Xf = pd.concat([Xf, pd.get_dummies(d["region"], dtype=float)], axis=1).to_numpy(float)
        o = d["pp_fire_cat_n"].fillna(0).to_numpy(float)
        lam = PoissonRegressor(alpha=1e-4, max_iter=500).fit(Xf, o).predict(Xf)
        k = 0.45 * lam
        c["fire_partial"] = pd.Series(np.where(o > 0, k / (o + k), 0.0), index=d.index)
        # F3(10/18 Fable): 消防ゼロの tract で「参照に署がある確率」を同じ λ で連続値にする
        f0 = (o == 0) & (c["fire_misfiled"].to_numpy(float) == 0) if "fire_misfiled" in c else (o == 0)
        c["fire0_q"] = pd.Series(np.where(f0, 1 - np.exp(-lam), 0.0), index=d.index)
        # 末尾の clip(0, 1) で 0/1 に潰れないよう、log1p(人口) を全体の最大で割って 0〜1 にする(10/18 夜に修正)
        lp = np.log1p(pop.to_numpy(float)) / np.log1p(pop.max())
        c["fire0_x_logpop"] = pd.Series(np.where(f0, lp, 0.0), index=d.index)
        s0 = ((d["pp_school_cat_n"].fillna(0) == 0) & (d["pp_school_misfiled_n"].fillna(0) == 0)).to_numpy()
        c["school0_x_logpop"] = pd.Series(np.where(s0, lp, 0.0), index=d.index)
        e0 = ((d["pp_ems_cat_n"].fillna(0) == 0) & (d["pp_ems_misfiled_n"].fillna(0) == 0)).to_numpy()
        c["ems0_x_logpop"] = pd.Series(np.where(e0, lp, 0.0), index=d.index)
        # F1: places に無い施設を建物の class / names で拾う(消防ゼロなのに消防の建物がある等)
        if "bf_fire_n" in d:
            c["fire0_bfire"] = pd.Series(f0 & (d["bf_fire_n"].to_numpy(float) > 0), index=d.index)
            c["school0_bschool"] = pd.Series(s0 & (d["bf_school_n"].to_numpy(float) > 0), index=d.index)
            c["fire1_bextra"] = pd.Series((o > 0) & (d["bf_fire_n"].to_numpy(float) > o), index=d.index)
            # 10/21 の延長: 学校ありでも建物が places の2倍超 / 農村の消防ゼロ∧消防の建物 / EMS ゼロ∧EMS の建物
            sc = d["pp_school_cat_n"].fillna(0).to_numpy(float)
            c["school1_bextra"] = pd.Series((sc > 0) & (d["bf_school_n"].to_numpy(float) > 2 * sc), index=d.index)
            c["fire0_bfire_rural"] = pd.Series(f0 & (d["bf_fire_n"].to_numpy(float) > 0)
                                               & (d["ur_class"] == "Rural").to_numpy(), index=d.index)
            c["ems0_bems"] = pd.Series(e0 & (d["bf_ems_n"].to_numpy(float) > 0), index=d.index)
        # F2: 消防ゼロだが境界の外 150 m / 50 m に消防の点(座標ずれで参照では自 tract) / 署が境界の内側 50 m(隣に取られうる)
        # F4: places の primary ではなく alternate にだけ消防・学校
        if "nb_fire150_n" in d:
            c["fire0_nb150"] = pd.Series(f0 & (d["nb_fire150_n"].to_numpy(float) > 0), index=d.index)
            c["fire0_nb50"] = pd.Series(f0 & (d["nb_fire50_n"].to_numpy(float) > 0), index=d.index)
            c["fire1_edge"] = pd.Series((o > 0) & (d["edge_fire50_n"].to_numpy(float) > 0), index=d.index)
            c["fire0_alt"] = pd.Series(f0 & (d["alt_fire_n"].to_numpy(float) > 0), index=d.index)
            c["school0_alt"] = pd.Series(s0 & (d["alt_school_n"].to_numpy(float) > 0), index=d.index)
    # 採点式の構造を持つ期待値モデルの予測(scripts/expected_model.py --write が書く。GEOID で結合)
    ye = P / "yhat_e.parquet"
    if ye.exists():
        c["yhat_e"] = d[["GEOID"]].merge(pd.read_parquet(ye), on="GEOID", how="left")["yhat_e"].fillna(0).set_axis(d.index)
    # 10/15 Fable の案③: 基準 v2 の予測 ŷ のビン(scripts/yhat_bins.py が書く)。最下位ビン(ŷ ≤ 0.02)は残りから決まる
    yb = P / "yhat_base.parquet"
    if yb.exists():
        y0 = d[["GEOID"]].merge(pd.read_parquet(yb), on="GEOID", how="left")["yhat_base"].set_axis(d.index)
        edges = [*BIN_EDGES, np.inf]
        for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:]), start=1):
            c[f"ybin{i}"] = ((y0 > lo) & (y0 <= hi)).astype(float)
    # 0〜1 の外の値は clip で黙って潰れる(10/18 に F3 の log1p(人口) が 0/1 の指示変数になった)。潰れる特徴を名指しする
    over = [k for k, v in c.items() if ((v.astype(float) > 1 + 1e-9) | (v.astype(float) < -1e-9)).mean() > 0.01]
    if over:
        warnings.warn(f"clip(0, 1) で 1% 超の行が潰れる特徴: {', '.join(sorted(over))}")
    return {k: v.astype(float).clip(0, 1) for k, v in c.items()}


def composite_v1(d: pd.DataFrame, k: float = 1.0, fire_q: pd.Series | None = None,
                 extra_km: pd.Series | None = None) -> pd.Series:
    """採点式と同じ「定義された成分だけの平均」で合成した推定値。

    道路: TIGER 近似(番号つき路線×重複倍率 + 境界15m帯)×k に対する Overture 幹線の比。基準0なら未定義。
    建物: Overture は MS 由来の足跡を含むので 0。建物が1棟以上なら定義。
    施設: 施設半分 = 消防・学校の定義された種別の平均、事業所半分 = 0(施設が1件以上なら定義)。
      消防: カテゴリ上の消防署あり→0 / なし・名前で消防署と分かる施設あり→1 / どちらもなし→未定義
      学校: 同じ規則(学校カテゴリ、名前で学校と分かる施設)
    fire_q: 「どちらもなし」の tract で基準側に消防署がある確率。与えると、消防=1(確率 q)と
      消防=未定義(確率 1-q)の合成値の期待値を返す。
    """
    nan = np.nan
    ref = (d["tg_num_in_mult_km"] + d["tg_num_ring15_km"] + (0 if extra_km is None else extra_km)) * k
    t = ratio_gap(d["tg_ov_hw_km"], ref)
    b = pd.Series(np.where(d["bldg_n"] > 0, 0.0, nan), index=d.index)
    school = np.where(d["pp_school_cat_n"] > 0, 0.0, np.where(d["pp_school_misfiled_n"] > 0, 1.0, nan))
    cbp = pd.Series(np.where(d["pp_poi_all_n"] > 0, 0.0, nan), index=d.index)

    def comp(fire: np.ndarray) -> pd.Series:
        hifld = pd.DataFrame({"f": fire, "s": school}, index=d.index).mean(axis=1)
        poi = pd.DataFrame({"h": hifld, "c": cbp}).mean(axis=1)
        return pd.DataFrame({"t": t, "b": b, "p": poi}).mean(axis=1).fillna(0)

    fire = np.where(d["pp_fire_cat_n"] > 0, 0.0, np.where(d["pp_fire_misfiled_n"] > 0, 1.0, nan))
    base = comp(fire)
    if fire_q is None:
        return base
    unknown = np.isnan(fire)
    q = fire_q.where(pd.Series(unknown, index=d.index), 0.0).fillna(0.0)
    return q * comp(np.where(unknown, 1.0, fire)) + (1 - q) * base


def moments(x: pd.Series) -> tuple[float, float]:
    x = x.to_numpy(dtype=float)
    return float(np.mean(x)), float(np.mean(x * x))
