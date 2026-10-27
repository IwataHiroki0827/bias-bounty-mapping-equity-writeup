"""Source Cooperative 上のデータを DuckDB でリモートのまま読むための接続ヘルパ。

ディスク空きが少ないので、原則ダウンロードせず集計だけをローカルに持つ。
CRS は OGC:CRS84(lon/lat)。距離・長さは ST_Transform(..., always_xy := true) を使うこと。
"""
from __future__ import annotations

import os

import duckdb

BASE = "s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
REGIONS = ["eastern-ok", "eastern-wa", "maricopa-az", "northern-ca", "south-central-tx"]


def connect(threads: int = 8) -> duckdb.DuckDBPyConnection:
    threads = int(os.environ.get("DUCKDB_THREADS", threads))  # 共有マシンでの上限(資源の申告値)
    con = duckdb.connect()
    for sql in ("INSTALL httpfs", "LOAD httpfs", "INSTALL spatial", "LOAD spatial",
                "SET s3_region='us-west-2'", "SET s3_url_style='path'", f"SET threads={threads}",
                "SET enable_progress_bar=false"):
        con.sql(sql)
    # 共有マシンでの上限(例: DUCKDB_MEMORY_LIMIT=3GB)。超えた分は DuckDB が一時ファイルへ逃がす
    if os.environ.get("DUCKDB_MEMORY_LIMIT"):
        con.sql(f"SET memory_limit='{os.environ['DUCKDB_MEMORY_LIMIT']}'")
    return con


def ref(region: str, layer: str) -> str:
    return f"'{BASE}/reference/{region}/{region}-{layer}.parquet'"


def strata(region: str, table: str = "strata-tract-table") -> str:
    return f"'{BASE}/strata/{region}/{region}-{table}.parquet'"
