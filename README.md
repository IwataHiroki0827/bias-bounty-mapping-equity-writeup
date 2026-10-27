# Bias Bounty: Mapping Equity Challenge (Zindi) — code for two write-ups

This repository holds everything behind two entries to the Zindi / Humane Intelligence
*Bias Bounty: Mapping Equity Challenge*. The submitted write-up is [`docs/writeup.md`](docs/writeup.md) (Part A
Documentation, Part B Bias Discovery; built from the two shorter versions by `python scripts/build_writeup.py`):

1. **Best Bias Discovery** — *whether a bus stop is on the open map depends on which agency runs the bus*.
   Twenty-two transit agencies' own GTFS stops (43,037) against Overture's transit features: Austin's network is 99%
   mapped, Houston's 15%. Write-up: [`docs/writeup_discovery_draft.md`](docs/writeup_discovery_draft.md).
2. **Best Documentation** — *estimating the coverage gap after the reference layers were withdrawn*: a label-free,
   rule-compliant estimator that measures each feature's correlation with the target from one aggregate leaderboard
   score, and combines features by the normal equations. Write-up:
   [`docs/writeup_documentation_draft.md`](docs/writeup_documentation_draft.md).

## Compliance in one paragraph

No TIGER/Line, Microsoft Building Footprints, HIFLD or CBP data is read anywhere, from the challenge bucket or any other
source. Submissions use only the Overture extracts, ACS housing and strata tables shipped with the challenge, plus our own
leaderboard probes (one public score per feature, never anything tract-level; the full record is
[`docs/probe_log.csv`](docs/probe_log.csv)). Aggregates other participants computed from the withdrawn layers are never
used to set a constant or a weight. External public data (GTFS feeds, ACS B08201) is used for the Bias Discovery entry
only, as the rules allow.

## Setup

Python 3.12, CPU only. On Windows, work in a short path (e.g. `C:\bbr`): pip fails with WinError 206 in deep folders.

```sh
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux/macOS: .venv/bin/pip
```

Remote reads use DuckDB against the public Source Cooperative bucket (no credentials). On a shared machine, cap DuckDB
with `DUCKDB_MEMORY_LIMIT=3GB` and `DUCKDB_THREADS=4`.

## Reproduce

**Bias Discovery — one command** (about 15 minutes; downloads the GTFS feeds and ACS table, rebuilds every table and
figure, then checks the write-up's headline numbers and prints PASS/FAIL for each):

```sh
python scripts/reproduce_discovery.py
```

The GTFS files' SHA-256 are recorded in [`docs/discovery_manifest.json`](docs/discovery_manifest.json), so a number that
drifts because an agency published a new feed can be told apart from a broken pipeline.

**Documentation — one command** (about 30 minutes from a fresh clone, mostly remote DuckDB reads; steps whose outputs
exist are skipped):

```sh
python scripts/reproduce_all.py
```

It builds every feature table (`build_features`, `discovery_sources`, `build_route_features`, `build_boundary_features`,
`build_tiger_proxy`, `build_poi_features`, `fetch_ruca`, `build_road_hyp`, `fetch_strata_extra`, `build_bldg_facility`,
`yhat_bins`), then re-derives every covariance from
[`docs/probe_log.csv`](docs/probe_log.csv) (the public scores the leaderboard returned, nothing else), solves the weights
and rebuilds every submitted combination, including the two final picks (lin_b2yf and alt_nofac). Submitted files are not in the repository, so the rebuilt CSV is checked against the
SHA-256 recorded at submission time in [`docs/submitted_hashes.json`](docs/submitted_hashes.json) (line endings normalised
to LF).

Tested from a clean clone on 2026-10-04: the Discovery check passed on every item and the rebuilt submission was
identical to the submitted file (maximum difference 0.0 over 9,794 tracts). The Discovery check was run again on 2026-10-27 from a fresh clone of this repository: 45 of 58 checks pass, and all 13 misses trace to the 10 GTFS feeds whose SHA-256 no longer matches `docs/discovery_manifest.json` (agencies republished them); the 12 unchanged feeds reproduce exactly. Tested again on 2026-10-25 (DuckDB capped at
2 GB): all five rebuilds match their recorded SHA-256 and both final picks are identical to the submitted files; about
29 minutes, peak memory 1.95 GB.

Measuring and fitting (these spend leaderboard submissions and need Zindi credentials in `.env`):

```sh
python scripts/probe.py <feature>@<scale> [--dry]   # one submission -> cov(feature, target); --dry only validates
python scripts/fit_linear.py <features...> --out submissions/<name>.csv
python scripts/fit_report.py                        # compare candidate feature sets
```

## Layout

| path | what |
|---|---|
| `src/features.py` | every candidate feature and the formula-shaped composite |
| `src/remote.py` | DuckDB connection to the challenge bucket |
| `scripts/probe.py`, `fit_linear.py`, `reproduce_submission.py` | the leaderboard-as-instrument method |
| `scripts/discovery_transit*.py`, `transit_*.py`, `reproduce_discovery.py` | the transit Discovery |
| `docs/` | write-ups, figures, probe log, evidence map, final-selection rule |

## Data and licences

Overture Maps (release 2026-08-19.0; transportation and buildings ODbL, places CDLA-Permissive-2.0; © OpenStreetMap
contributors, Overture Maps Foundation); ACS and strata tables as shipped with the challenge (public domain); USDA RUCA
2020; GTFS feeds via the Mobility Database and agency sites (sources and retrieval dates in the Discovery write-up).

## Secrets

Credentials live only in `.env` (git-ignored); `.env.example` lists key names without values. A pre-commit hook
(`.githooks/pre-commit`, enabled by `sh scripts/setup.sh`) blocks secret files and token-shaped strings.

## Licence

Code: MIT (see `LICENSE`). Data keep their own licences, listed above and in `docs/gtfs_licenses.md`.
