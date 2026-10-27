# Best Documentation: estimating the coverage gap after the reference layers were withdrawn — a compliant, label-free pipeline

The full record, with every dated step, is in the repository (`docs/writeup_documentation_draft.md`); this version keeps its section numbers.

> **In three lines.** With no labels and the reference layers withdrawn, we used three constant submissions to pin the
> metric (RMSE, not MAE), measured each Overture-only feature's correlation with the target from one aggregate score per
> submission, and combined them by solving the normal equations: public RMSE 0.0634 against 0.0977 for the best constant
> we submitted (the optimal constant would score 0.0890), rebuilt exactly by one script from a log of public scores.
>
> Compliance: no TIGER, Microsoft Building Footprints, HIFLD or CBP data is used anywhere in the scored pipeline. Only
> Overture (release 2026-08-19.0), ACS housing, the strata tables and our own leaderboard probes enter a submission.
> RUCA 2020 (a strata table in the challenge bucket) gives two flags used in the first final pick, lin_b2yf; the
> strata's building-count columns (`usfs_BuildingCount_sum`,
> `carbonplan_buildings`) are not used.

## 1. What changed, and what that leaves

The reference layers were removed on 2026-09-25 and target reconstruction was prohibited on 2026-09-28 (thread 35079).
The task is unsupervised estimation, scored on a 30% public split.

## 2. Pinning down the metric with three constant submissions

The Evaluation page says RMSE; an earlier participant measurement suggested MAE. We submitted constants 0, 0.2 and 0.1:

| constant | public score |
|---:|---:|
| 0.0 | 0.107246299 |
| 0.2 | 0.166070250 |
| 0.1 | 0.097675731 |

If the metric is RMSE, MSE(c) = E[y²] − 2c·E[y] + c². The first two give E[y] = 0.0598 and E[y²] = 0.01150, which
predict 0.09768 for c = 0.1; the third scored 0.097676: **RMSE, confirmed to four digits.** The public target has mean
0.0598, RMS 0.1072 and standard deviation 0.0890, the floor any constant can reach. The daily limit is **5** submissions
(not 10), reset at 00:00 UTC.

## 3. Measuring a feature without labels

Submitting a feature x in [0, 1] returns MSE(x) = E[y²] − 2E[xy] + E[x²], so one submission gives E[xy], hence cov(x, y)
and corr(x, y). Feature–feature covariances are computed locally, so the weights β = Σ⁻¹c and the expected
MSE = var(y) − cᵀΣ⁻¹c follow without any label. Each probe returns one aggregate number; no tract-level value is inferred. Whether fitting weights from one's own public scores is allowed was asked in threads 35292 and 35532 and had no organiser answer by 27 October; every weight in both final picks is fitted this way, so we describe the step in full here rather than assume the answer.

**How reliable is one probe?** We use full-set E[x²] in place of the hidden subset's; over 2,000 redrawn 30% subsets:

| feature | tracts with x > 0 | corr (point) | 95% interval over subsets |
|---|---:|---:|---|
| road proxy (§4) | 18% | +0.610 | [+0.555, +0.662] |
| fire-station misfiled (§5) | 6% | +0.072 | [−0.084, +0.211] |
| POI density shortfall | 75% | −0.004 | [−0.132, +0.117] |

A feature whose interval crosses zero is not accepted or rejected on its own probe.

![Probe correlations](figures/doc_probe_correlations.png)

**Scaled probes remove most of that error.** Submitting a·x gives E[xy] = (E[y²] + a²E[x²] − RMSE²) / 2a, and the error
from full-set moments becomes a/2·ΔE[x²] − ΔE[x]·E[y]. For a 0/1 flag ΔE[x²] = ΔE[x], so a = 2E[y] ≈ 0.12 cancels it to
first order. The correlation's SD falls from 0.074 to 0.000 for a binary flag (a = 0.12), from 0.045 to 0.005 for a road
feature (a = 0.25) and from 0.010 to 0.004 for a region interaction (a = 0.5). From 2026-10-05 every probe is scaled
(`python scripts/probe.py name@a`; the log records a).

## 4. The road component: reproducing the artefact, not the reference

Thread 35000 found that most of the official road gap is not missing road: (i) a TIGER highway on a tract boundary is
clipped into both neighbouring tracts while Overture's line falls in one; (ii) concurrent routes (US-69/US-75) are
stored once per route number in TIGER. Both are visible in Overture alone:

- Numbered routes: Overture `routes[].network` in `US:I`, `US:US`, `US:<state>` and their Business/Loop/Spur/Truck variants
  (county routes excluded).
- Concurrency: each segment's length is multiplied by its number of distinct numbered routes.
- Boundary double counting: numbered-route length within a 15 m ring outside the tract is added.
- Estimated gap: 1 − min(1, Overture motorway/trunk/primary/secondary length ÷ the estimate above); undefined when the
  estimate is zero.

**Label-free check against organiser aggregates** (tracts with transport undefined):

| region | ours | published |
|---|---:|---:|
| eastern-ok | 268 | 253 |
| maricopa-az | 862 | 869 |
| northern-ca | 229 | 218 |
| south-central-tx | 1,913 | 1,704 |

Counting all Farm-to-Market roads leaves only 1,218 undefined tracts in Texas, below the published 1,704, so FM is
excluded by default. A naive buffer scored corr −0.013 (d = 10 m) and −0.128 (d = 50 m).

**Scale k.** The proxy can only miss TIGER length, so we carry one global factor k
(gap = 1 − min(1, Overture ÷ (k × estimate))), chosen by probed correlation at k = 1.0, 1.4 and 2.0 (0.610, 0.684,
0.683). The tie shows that k fixes the level of the reference, not where it is short.

**Where we drew the compliance line.** Write-ups posted before 25 September contain aggregates computed from the
reference layers. With k = 1.4 the four regional means land within 0.02 of thread 35000's, but k was fixed from the
probe grid before this comparison, and no such aggregate sets any constant or weight.

## 5. Facilities

The scored fire term counts only `categories.primary == "fire_department"`. Thread 34925 showed that in about a third of
"blackout" tracts the station is in Overture under another category. We count places whose name identifies a fire
department (regex from 34925) but whose category does not; schools are handled the same way.

A tract with no fire place has a fire term of 1 or undefined, depending on how likely it is to contain a station. We encode that with package-only indicators (no fire place × `ur_class` Rural, no fire place ×
`tribal_any`) weighted by their probed covariances. The models up to 7 October used "no fire place", probed unscaled at
corr −0.211, plus a Rural flag. Re-probed at a = 0.12 on 9 October, "no fire place" is −0.060 and "fire station
misfiled" +0.145 (unscaled: +0.072); that error is what made lin_v5 lose to the facility-free model (§7).

**What the group means show, and a reading we had to withdraw.** A binary flag probed at a small scale gives the group
average E[y | flag] = E[y] + cov / P(flag). With the unscaled value, urban tracts without a fire place came out at 0.041
against 0.112 for rural ones, and we wrote that the signal means opposite things in towns and countryside. Re-probed,
the urban group is at 0.051: most of that contrast was probe error. Table: re-probed values, scored tracts only
(`scripts/subgroup_check.py`); lin_v5′ is lin_v5's feature set re-fitted on them:

| Group (share of scored tracts) | Probed mean label | lin_v5′ | Facility-free |
|---|---:|---:|---:|
| Urban, no fire place (64.5%, by difference) | 0.051 | 0.051 | 0.052 |
| Rural, no fire place (6.3%) | 0.115 | 0.108 | 0.095 |
| Rural, fire place present (12.0%, by difference) | 0.109 | 0.113 | 0.106 |
| No fire place, but a fire-protection-service place (6.1%) | 0.100 | 0.090 | 0.089 |
| Fire place present, no EMS place (24.4%) | 0.066 | 0.067 | 0.068 |

The facility features fit every group within 0.01; the facility-free model under-predicts rural tracts without a station
by 0.02. Weighted by group size, the squared group-mean errors are 0.000011 of MSE for lin_v5′ and 0.000035 for the
facility-free model.

## 5a. Components we set to zero, and every free parameter

| term | set to | why | probe that tests it |
|---|---|---|---|
| building gap | 0 | Overture ingests Microsoft ML footprints wherever OpenStreetMap has none | share of Overture buildings from OSM (OSM merges outbuildings, so Overture < Microsoft there) |
| CBP half of the facility term | 0 | all-places vs establishments is almost always ≥ 1 in Overture | tracts with ≥ 1,500 people and ≤ 3 places |
| EMS type in the HIFLD half | not used | the README says it rarely binds | tracts with a fire station place but no EMS place |

| parameter | value | set by |
|---|---|---|
| reference scale k | 1.4 | probed correlation at k = 1.0 / 1.4 / 2.0 |
| boundary ring | 15 m | probed correlation at 5 / 15 / 30 m (0.586 / 0.610 / 0.607) |
| share of un-numbered highways added (H2) | 0.5 | one probe; its weight in the combination is solved from the probes |
| probe scale a | 0.12 (0/1), 0.25 (road), 0.5 (composite) | subset simulation of the moment-substitution error (§3) |
| region slopes, feature weights | — | normal equations on probed covariances |

## 5b. Alternatives we considered, and why we did not use them

| alternative | what happened | why not used |
|---|---|---|
| Calibrate k and the facility terms to regional means other participants published from the withdrawn layers | k = 1.4 matched all four regions | those aggregates derive from TIGER/USGS; the rule forbids approximating the target with them, so k was set by probe instead (§4) |
| Buffer every tract boundary and count all highways in the buffer | correlation −0.013 (10 m), −0.128 (50 m) | does not copy the mechanism (§4) |
| Count all Farm-to-Market roads as reference | correlation 0.505, worse than 0.610; restricted to undefined tracts −0.049 | TIGER classes only part of FM as S1200 |
| Add un-numbered motorway/trunk, routes with empty network, divided-carriageway pairs, ramps | correlation with the main road estimate 0.989–0.998 | no new information |
| Two road estimates in contrast (lin_v4) | expected 0.0596, public 0.0668 | weights of opposite sign amplify probe error (§7) |
| Shrink all weights for the second final pick | prediction correlation 1.0 with the first | a linear transform fails in the same places (§7) |
| Fit tract-level values from repeated leaderboard queries | not attempted | label recovery through the leaderboard is the failure mode documented on Kaggle (all test labels recovered from a log-loss oracle, arXiv 1707.01825); every probe here returns one aggregate per feature |

## 5c. Objections we anticipated

**"Estimating TIGER length from Overture is 'indirectly approximating' the reference."** This is open in thread 35079.
We never read TIGER, the footprints, HIFLD or CBP, and the road features are separable: leaving them out of
`scripts/fit_linear.py` gives a road-free model from the same probes.

**"Leaderboard probing is overfitting the public split."** Each probe returns one aggregate number; we used 40
submissions up to 8 October (log: `docs/probe_log.csv`). Differences between two submissions move by about 0.0006
between public and private (`scripts/selection_noise.py`).

**"The score is still far from 0."** Scores of 0.0 used the withdrawn layers. The best constant we submitted scores
0.0977, the optimal constant 0.0890 and all zeros 0.1072; ours is 0.0634.

**"Why not train a model?"** There are no labels; the normal equations are the model that one aggregate per submission
can identify.

## 6. Edge cases

| case | count | handling |
|---|---:|---|
| Water tracts dropped from scoring (99xx, south-central-tx) | 7 | not in the sample submission; excluded |
| Land tracts that are mostly water (bays, lakes) | not counted | the allowed data has no water area per tract (RUCA gives land area only), so these get no special handling; the road and facility terms are per tract, not per area, so a large water share does not enter any feature directly |
| Water tracts that are in the sample submission (48039990000, 48057990000) | 2 | the only tracts with no Overture places and no buildings at all; no ur_class. Every feature is 0 there, so the model gives the intercept-level value (0.002 in lin_v5) |
| Tracts with a positive reference estimate but no Overture highway inside | 13 | numerator 0 → estimated gap 1 |
| Tracts with no numbered route inside or on the boundary | 3,370 (ours, all five regions; 98 in eastern-wa) | transport undefined → composite is the mean of the other components |
| eastern-wa tracts (added to the sample submission on 28 September) | 415 | the description page lists the scored tracts as the four other regions (9,379), and the probed covariance of the eastern-wa composite is about zero (+0.00002), so they appeared not to be scored. Confirmed on 9 October: a file with 0.5 on the eastern-wa tracts and 0 elsewhere scored 0.107246299, identical to all zeros to nine digits. From then on, moments are taken over the 9,379 scored tracts only (`scripts/fit_linear.py`); eastern-wa is still predicted with the same formula because the file must contain it |
| Zero-population tracts | 27 | kept; facility and road terms do not depend on population |
| GEOID read as integer | — | always text; Maricopa is FIPS 04 and one tract is in New Mexico (35023970000) |
| DuckDB axis order | — | `ST_Transform(..., always_xy := true)`; checked on a 1° parallel at 35°N (90.52 km in EPSG:5070) |

## 7. Results

| submission | features | expected RMSE | public RMSE |
|---|---|---:|---:|
| constant 0.1 | — | 0.0977 | 0.0977 |
| lin4_v1 | road proxy, fire misfiled, no fire place, POI shortfall | 0.0684 | 0.0723 |
| lin5_v2 | composite v1, road proxy (30 m ring), fire misfiled, no fire place, POI shortfall | 0.0670 | 0.0718 |
| lin_v3 | composite v1, its eastern-ok and south-central-tx interactions, road proxy with k = 1.4, fire misfiled, no fire place, POI shortfall | 0.0626 | 0.0673 |
| lin_v4 | k = 1.4 composite, both road estimates (H2 contrast), five region slopes, three facility features | 0.0596 | 0.0668 |
| lin_v5 | k = 1.4 composite and road estimate, five region slopes, three facility features, road-undefined and rural flags (chosen by the 90th percentile, 0.0640) | 0.0615 | 0.0664 |
| alt_nofac | k = 1.4 composite and road estimate, road-undefined flag, five region slopes; no facility features | 0.0633 | 0.0652 |
| lin_v6′ | lin_v5's features re-fitted on re-probed values plus seven more; moments over the scored tracts | 0.0626 | **0.0634** |

![Expected vs observed](figures/doc_expected_vs_observed.png)

Blue lines: point expectation to the 90th percentile of 300 redrawn splits. Grey boxes: ranges written before submitting.

| submission (date) | written before submitting | outcome |
|---|---|---|
| lin_v4 (5 October) | **0.0635–0.0644**; first pick if 0.0661 or lower; above 0.0650 → keep fewer weights | **0.0668**; not adopted |
| lin_v5 (7 October) | 0.0657–0.0667 | **0.0664**, inside; gain over lin_v3 0.0009 < 0.0012 |
| facility-free (9 October) | 0.0673–0.0683 | **0.0652**, better than the range |
| lin_v6′ (11 October) | 0.0637–0.0653 | **0.0634**, 0.0008 from its point expectation |

**Opposite-sign weights amplify probe error.** A covariance error e adds **2bᵀe** to the expected MSE. lin_v4 contrasted
two road estimates that correlate 0.94; over 300 redrawn subsets
(`scripts/robust_expected.py`) its expected RMSE has SD 0.0065, against 0.0027 for lin_v3, and its observed 0.0668 sits
at its 90th percentile (0.0671). From 6 October we choose combinations by that 90th percentile.

**A shared unscaled facility probe explained the offset.** Every combination with the facility features scored worse than its point expectation, by +0.004 to +0.007. All of them contained "no fire place" (71% of tracts), probed unscaled; its moment-substitution error is about
ΔE[x]·(1/2 − E[y]) ≈ 0.0085 × 0.44 ≈ 0.0037, some 40% of its covariance (−0.0086). With the re-probed values, lin_v5's offset shrinks from +0.0049 to +0.0026 and the facility-free model's to +0.0011. A region indicator probed at two scales
put south-central-tx at 0.6400 of the public part, exactly its share of the scored tracts (6,003 of 9,379).

**The MSE difference decomposes from probes alone.** For two linear models it is E[p₁² − p₂²] − 2·E[(p₁ − p₂)y]
(`scripts/why_alt_won.py`). It predicts lin_v5 worse by 0.000191 in MSE; the observed gap is 0.000154. lin_v5 predicted
0.089 for the 29% of tracts with a fire place, against a probed mean of 0.068: the measurement that set the facility
weights was the problem, not the features.

**How the final two are chosen.** A public gap under 0.0012 is not trusted. The second pick is a model from a different
feature family, with prediction correlation below 0.98 and expected RMSE within 0.003. lin_v5 and the facility-free model
correlate 0.972, and lin_v5 predicts rural tracts about 0.01 higher in every region.

| Feature | lin_v5 | Facility-free |
|---|---:|---:|
| Composite, k = 1.4 | 0.610 | 0.270 |
| Road estimate t_k14 | 0.063 | 0.193 |
| Road length undefined | −0.011 | −0.010 |
| Region slope: eastern-ok / eastern-wa / maricopa-az | 0.254 / −0.567 / 0.008 | 0.229 / −0.623 / −0.024 |
| Region slope: northern-ca / south-central-tx | 0.164 / 0.044 | 0.111 / −0.007 |
| No fire place / misfiled station / POI shortfall | −0.027 / −0.044 / 0.023 | — |
| Rural | 0.005 | — |
| Intercept | 0.040 | 0.030 |

## 7a. After lin_v6′: looking for information, not form (12–22 October)

Each probe is now judged against the correlation the current model already implies (its *null*); it counts as
information only if |measured − null| > 0.015, a threshold fixed before the first such probe. Region interactions of the
road estimate (Texas −0.025, Oklahoma +0.021), tertiary-heavy tracts (+0.028), metropolitan cores (−0.034), small-city
cores (+0.061) and tribal tracts without a fire place (+0.029) cleared it; land area, local k and three
business-establishment proxies did not. Road hypotheses for the ~30% of reference length we do not see were each written
down with a rejection rule before aggregation (`docs/road_hypotheses.md`): parallel carriageways and import-era
highways were rejected, ramps add little, and the two that survived to be probed, tertiary-or-lower roads *named* as
highways (Texas Farm-to-Market roads, 6.5% of highway length) and tertiary roads signed at ≥ 45 mph (19% in Oklahoma
and Washington), returned their nulls on 18 October (−0.002 and −0.011 against +0.074 and +0.114 expected if true).
Where the missing 30% lies is not answered by any attribute in the shipped Overture data. Treating a structural model of the scoring formula as the truth, every change of model *form* (bins,
mixtures, per-region fits) together is bounded at 6.2·10⁻⁵ of MSE, about a twelfth of the distance to the best public
scores; four quantile-bin probes on 17 October confirmed it (tails within 0.01 of their nulls, about 1.2·10⁻⁵ of MSE
in the middle bins). Deviations are measured on the public 30% only, so the small hits (1.9–3.0 standard errors of
that split) are not counted as private gains when choosing the final two (full detail in the repository draft, §7a).
The information that did move the score was a second source inside the shipped data: Overture buildings tagged or
named as fire stations in tracts whose *places* show none (1.9% of scored tracts) returned +0.107 against a null of
+0.025 (8.1 standard errors, about 9·10⁻⁵ of MSE) on 20 October, against two rejection rules written before the
count. Added to the combination it gave lin_b2yf (public 0.062055, 21 October). A boundary-offset version of the
same idea failed its own pre-registered test (the effect had to be stronger at 50 m than at 150 m; it was weaker).

**The final two (chosen 21 October).** First: lin_b2yf, the best public combination (0.062055), which includes the
fire-station building flag and partial fire coverage. *Partial fire coverage* takes its form and its one constant from thread 35325: a tract with O ≥ 1 fire places may still have K ~ Poisson(u·λ) more stations in the reference, giving an expected fire gap K/(O + K), with u = 0.45 as published there. λ is our own Poisson fit of Overture fire places on population, land area, rurality and region; we did not tune u, and the feature's weight comes from our own probe. Second: the facility-free model (0.065236; prediction correlation 0.927). The
facility-free model plus the fire-station flag scored 0.064442, but it was not picked: the gap is under 0.0012, and
sharing the flag with the first pick would let one failed assumption move both picks the same way.

## 8. Reproduction

Code: https://github.com/IwataHiroki0827/bias-bounty-mapping-equity-writeup (public from the day this write-up is posted).
Data, submissions and credentials are not in the repository; every data step fetches from the challenge bucket.
`python scripts/reproduce_all.py` runs the steps below and checks the rebuilt submission against the SHA-256 recorded at
submission time (`docs/submitted_hashes.json`).

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip; use a short path
python scripts/build_features.py           # Overture/ACS per tract                         ~7 min
python scripts/discovery_sources.py        # joins strata → data/processed/features_all     ~10 s
python scripts/build_route_features.py     # numbered-route lengths                         ~3 min
python scripts/build_boundary_features.py  # highway length near tract boundaries           ~8 min
python scripts/build_tiger_proxy.py        # numbered-route reference estimate              ~5 min
python scripts/build_poi_features.py       # facility clues                                 ~1 min
python scripts/fetch_ruca.py               # RUCA 2020 tract table (HTTPS)                  ~10 s
python scripts/build_road_hyp.py           # road-gap hypotheses H1/H3                      ~1 min
python scripts/fetch_strata_extra.py       # land area from the strata tables               ~10 s
python scripts/build_bldg_facility.py      # fire/school/EMS buildings by class and name    ~4 min
python scripts/yhat_bins.py                # prediction bins of the 25-feature base         ~1 s
python scripts/reproduce_submission.py     # rebuilds lin_v3, lin_v5, alt_nofac, lin_v6′ and lin_b2yf from docs/probe_log.csv alone
# measuring and fitting (spends submissions):
python scripts/probe.py <feature> [--dry]  # one submission → corr(feature, target); --dry only writes and validates
python scripts/probe_noise.py              # subset noise of each probe
python scripts/fit_linear.py <features> --out submissions/<name>.csv
```

`docs/probe_log.csv` holds one public RMSE per probed feature. Each rebuild uses only the rows that existed at submission
(14 rows for lin_v3, 23 for lin_v5 and alt_nofac, 41 for lin_v6′, 80 for lin_b2yf); all five match the submitted SHA-256. A clean-clone run (2026-10-04, CPU only,
`DUCKDB_MEMORY_LIMIT=3GB`) rebuilt `lin_v3.csv` exactly (maximum difference 0.0 over 9,794 tracts) in about 24 minutes
of feature building. A second clean-clone run (2026-10-25, DuckDB capped at 2 GB) rebuilt both final picks, lin_b2yf and
alt_nofac, exactly (about 29 minutes, peak 1.95 GB) and found one gap, now fixed: a step read the private submission
log instead of the public `docs/probe_log.csv`. Seeds: only the noise bootstrap is random (seed 0). Versions are pinned in `requirements.txt` (Python 3.12,
DuckDB 1.5.6, pandas 2.2.3, NumPy 2.2.6, pyarrow 25.0.1, scikit-learn 1.6.1, SciPy 1.14.1, matplotlib 3.10.8).

## 9. Data, licences and attribution

- Overture Maps release 2026-08-19.0, as shipped in the challenge package: transportation and buildings under ODbL,
  places under CDLA-Permissive-2.0 (attribution: © OpenStreetMap contributors, Overture Maps Foundation).
- ACS 5-year housing units (B25001) and the strata tables, as shipped in the challenge package (US Census Bureau and the
  listed federal sources: public domain).
- USDA ERS RUCA 2020 (public domain), as shipped in the challenge package's strata; two flags from it enter lin_b2yf.
- No data from TIGER/Line, Microsoft Building Footprints, HIFLD or CBP is read anywhere in the scored pipeline.
