# Best Documentation: estimating the coverage gap after the reference layers were withdrawn — a compliant, label-free pipeline

> **In three lines.** With no labels and the reference layers withdrawn, we used three constant submissions to pin the
> metric (RMSE, not the MAE the forum assumed), then measured each Overture-only feature's correlation with the target
> from one aggregate score per submission, and combined them by solving the normal equations: public RMSE 0.0634 against
> 0.0977 for the best constant we submitted (the optimal constant would score 0.0890), rebuilt exactly by one script
> from a log of public scores (one number per probe).
>
> Compliance: no TIGER, Microsoft Building Footprints, HIFLD or CBP data is used anywhere in the scored pipeline,
> neither from the challenge package nor from any other source. Only Overture (release 2026-08-19.0), ACS housing,
> the strata tables and our own leaderboard probes enter a submission. Organiser-published aggregates on the challenge
> pages (per-region undefined counts) are used only as a check on the road estimate, never to set a weight.
> The USDA RUCA 2020 tract table (`fetch_ruca.py`) is one of the strata tables shipped in the challenge bucket; two
> flags built from it (small-city cores, metropolitan cores) enter the first final pick, lin_b2yf. The strata's
> building-count columns (`usfs_BuildingCount_sum`, `carbonplan_buildings`), questioned in
> thread 35079 because they may derive from footprints, are not used at all.

## 1. What changed, and what that leaves

On 2026-09-25 the reference layers were removed and on 2026-09-28 (thread 35079) target reconstruction was prohibited.
No labels have ever been published. The task is therefore unsupervised estimation, scored by RMSE on a 30% public split.
This writeup documents how we (a) pinned down the metric and the target's moments without labels, (b) built features
from the mechanisms that produce the gap, using only Overture's own attributes, and (c) combined them with a model
whose expected score is computed before each submission.

## 2. Pinning down the metric with three constant submissions

The Evaluation page says RMSE; an earlier participant measurement suggested MAE. With the current evaluation set
(after the 28 September update) we submitted constants 0, 0.2 and 0.1:

| constant | public score |
|---:|---:|
| 0.0 | 0.107246299 |
| 0.2 | 0.166070250 |
| 0.1 | 0.097675731 |

If the metric is RMSE, MSE(c) = E[y²] − 2c·E[y] + c². The first two give E[y] = 0.0598 and E[y²] = 0.01150, which
predict 0.09768 for c = 0.1. The third submission scored 0.097676: **RMSE, confirmed to four digits.**
The public target has mean 0.0598, RMS 0.1072 and standard deviation 0.0890, so 0.0890 is the floor any constant can reach.

One other page statement also disagreed with measurement: the daily limit is **5** submissions (not 10), reset at 00:00 UTC.

## 3. Measuring a feature without labels

For any feature x in [0, 1], submitting x itself returns MSE(x) = E[y²] − 2E[xy] + E[x²]. With E[y²] known, one
submission gives E[xy], hence cov(x, y) and corr(x, y). Feature–feature covariances are computed locally, so the
least-squares weights β = Σ⁻¹c and the expected MSE = var(y) − cᵀΣ⁻¹c follow without any label.
Each probe returns one aggregate number; no tract-level value is ever inferred. Whether fitting weights from one's own public scores is allowed was asked in threads 35292 and 35532 and had no organiser answer by 27 October; every weight in both final picks is fitted this way, so we describe the step in full here rather than assume the answer.

**How reliable is one probe?** E[x²] should be taken over the hidden public subset, which is unknown, so we use the
full-set value. We measured the resulting error by redrawing random 30% subsets 2,000 times:

| feature | tracts with x > 0 | corr (point) | 95% interval over subsets |
|---|---:|---:|---|
| road proxy (§4) | 18% | +0.610 | [+0.555, +0.662] |
| fire-station misfiled (§5) | 6% | +0.072 | [−0.084, +0.211] |
| POI density shortfall | 75% | −0.004 | [−0.132, +0.117] |

Rule we followed: a feature whose interval crosses zero is not accepted or rejected on its own probe.

![Probe correlations](figures/doc_probe_correlations.png)

**Scaled probes remove most of that error.** Submitting a·x instead of x gives
E[xy] = (E[y²] + a²E[x²] − RMSE²) / 2a, and the error from using full-set moments becomes
a/2·ΔE[x²] − ΔE[x]·E[y]. For a 0/1 flag ΔE[x²] = ΔE[x], so a = 2E[y] ≈ 0.12 cancels it to first order. Redrawing the
30% subset 2,000 times, the correlation's SD falls from 0.074 to 0.000 for a binary flag (a = 0.12), from 0.045 to 0.005
for a road feature (a = 0.25) and from 0.010 to 0.004 for a region interaction (a = 0.5). It is still one submission and
one aggregate number per feature; what remains is the genuine difference between the public 30% and the private 70%.
From 2026-10-05 every probe is scaled (`python scripts/probe.py name@a`; the log records a).

## 4. The road component: reproducing the artefact, not the reference

Thread 35000 decomposed the official road gap (when the reference was available) and found most of it is not missing
road: (i) tract boundaries follow highways, so a TIGER highway on the boundary is clipped into both neighbouring tracts
while Overture's line falls in one; (ii) concurrent routes (US-69/US-75) are stored once per route number in TIGER.
Both mechanisms are visible in Overture alone:

- Numbered routes: Overture `routes[].network` in `US:I`, `US:US`, `US:<state>` and their Business/Loop/Spur/Truck variants
  (county routes excluded).
- Concurrency: each segment's length is multiplied by its number of distinct numbered routes.
- Boundary double counting: numbered-route length within a 15 m ring outside the tract is added.
- Estimated gap: 1 − min(1, Overture motorway/trunk/primary/secondary length ÷ the estimate above); undefined when the
  estimate is zero.

**Label-free check against organiser aggregates.** The number of tracts with no named-highway reference (transport undefined):

| region | ours | published |
|---|---:|---:|
| eastern-ok | 268 | 253 |
| maricopa-az | 862 | 869 |
| northern-ca | 229 | 218 |
| south-central-tx | 1,913 | 1,704 |

Texas is the outlier because TIGER classes part of the Farm-to-Market network as S1200. Counting all FM roads as reference
leaves only 1,218 undefined tracts, below the published 1,704, so FM is excluded by default and tested as a variant.

A naive version (buffer the tract by d metres and count all highways) scored corr −0.013 (d = 10 m) and −0.128 (d = 50 m):
the mechanism has to be copied exactly, or the signal disappears.

**What differs from other label-free estimators.** Thread 35155 approximates the same reference from the same Overture
route attributes. We add the two mechanisms thread 35000 identified (the concurrency multiplier and the boundary ring),
choose the scale factor k by probe rather than by assumption, and weight every feature by its measured covariance; the
naive buffer version above shows how much the mechanism matters.

**Scale of the reference estimate.** The numbered-route proxy can only miss TIGER length (county-highway S1200 segments,
Overture segments without route relations), never add it, so the true reference is probably longer than our estimate.
We therefore carry one global factor k on the reference (gap = 1 − min(1, Overture ÷ (k × estimate))) and choose it by
the probed correlation (§3) at k = 1.0, 1.4 and 2.0 (0.610, 0.684, 0.683): one global parameter, ordinary leaderboard use,
no per-tract or per-group probing. That k = 1.4 and 2.0 tie is itself informative: a scale factor only moves which
tracts cross ratio 1, so it fixes the level of the reference, not the places where it is short.

**Where we drew the compliance line.** Several write-ups posted before 25 September contain aggregates computed from the
reference layers themselves (mean official road gap per region, fire-station counts per tribal area). They would have
pinned k and the facility terms without spending a submission, and our estimate is consistent with them (with k = 1.4
the four regional means land within 0.02 of thread 35000's). We do not use them to set any constant or weight: they are
derived from the withdrawn layers, and the 28 September rule forbids using those layers to approximate the target
"directly or indirectly". They appear here only as an after-the-fact level check: k was fixed from the probe grid before this comparison was made,
and the comparison would not have changed it. Every number that enters a submission comes from the package
(Overture, ACS, strata) or from our own probes.

## 5. Facilities

The scored fire term counts only `categories.primary == "fire_department"`. Thread 34925 showed that in about a third of
"blackout" tracts the station is in Overture under another category. We count, per tract, places whose name identifies a
fire department (regex from 34925) but whose category does not; a tract with such a place and no `fire_department`
place is likely to score a fire gap of 1. Schools are handled the same way.

The harder case is a tract with no fire place at all, named or categorised. Its fire term is either 1 (the reference has
a station Overture lacks) or undefined (there is no station). Setting it to undefined, as a first version did, assumes the
first never happens. Where it happens depends on how likely a tract is to contain a station at all, which rises with
tract size and rurality. We encode that as indicators from the package only (no fire place × `ur_class` Rural, and no
fire place × `tribal_any`) and let their probed covariances set their weights, rather than plugging in a probability
taken from someone else's count of the withdrawn fire-station layer. The models submitted up to 7 October used the plain
"no fire place" indicator, probed unscaled in the first days at corr −0.211, plus a Rural flag. Re-probed at a = 0.12 on
9 October, "no fire place" is −0.060 and "fire station misfiled" +0.145 (unscaled: +0.072): the unscaled values were off
by far more than their intervals suggested, and that error is what made lin_v5 lose to the facility-free model (§7).
The Rural interaction was probed scaled on 7 October (+0.155); the tribal interaction has not been probed. The POI
shortfall (unscaled −0.004) is re-probed on 10 October.

**What the group means show, and a reading we had to withdraw.** A binary flag probed at a small scale gives its
covariance with the label, and with it the mean label of the flagged group: E[y | flag] = E[y] + cov / P(flag), a group
average over hundreds or thousands of tracts, never a per-tract value. With the unscaled "no fire place" value, urban
tracts without a fire place came out at 0.041 against 0.112 for rural ones, and we wrote that the same signal means
opposite things in towns and in the countryside. With the re-probed value the urban group is at 0.051: most of that
contrast was the probe error, and what remains is the ordinary urban/rural difference. The table uses the re-probed
values and moments over the scored tracts only (`scripts/subgroup_check.py`); lin_v5′ is lin_v5's feature set re-fitted
on them:

| Group (share of scored tracts) | Probed mean label | lin_v5′ | Facility-free |
|---|---:|---:|---:|
| Urban, no fire place (64.5%, by difference) | 0.051 | 0.051 | 0.052 |
| Rural, no fire place (6.3%) | 0.115 | 0.108 | 0.095 |
| Rural, fire place present (12.0%, by difference) | 0.109 | 0.113 | 0.106 |
| No fire place, but a fire-protection-service place (6.1%) | 0.100 | 0.090 | 0.089 |
| Fire place present, no EMS place (24.4%) | 0.066 | 0.067 | 0.068 |

Re-fitted on correct values, the facility features fit every group within 0.01; the facility-free model under-predicts
rural tracts without a station by 0.02. Weighted by group size, the squared group-mean errors are 0.000011 of MSE for
lin_v5′ and 0.000035 for the facility-free model (groups overlap, so these are sizes, not a decomposition).

## 5a. Components we set to zero, and every free parameter

The composite follows the published formula, but three of its terms have no usable signal in the allowed data, so they
are fixed at zero. Each is now a scheduled probe in its own right, so the assumption is tested, not just stated (results in §7):

| term | set to | why | probe that tests it |
|---|---|---|---|
| building gap | 0 | Overture ingests Microsoft ML footprints wherever OpenStreetMap has none | share of Overture buildings from OSM (OSM merges outbuildings, so Overture < Microsoft there) |
| CBP half of the facility term | 0 | all-places vs establishments is almost always ≥ 1 in Overture | tracts with ≥ 1,500 people and ≤ 3 places |
| EMS type in the HIFLD half | not used | the README says it rarely binds | tracts with a fire station place but no EMS place |

Every free parameter and how it was set (none from a published aggregate of the withdrawn layers):

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

**"Estimating TIGER highway length from Overture is itself 'indirectly approximating' the reference."** This is the
open question in thread 35079 (several participants asked; no answer yet), so we state our reading rather than assume
it. The rule forbids *using the reference datasets* to recreate the target. We never read TIGER, the footprints, HIFLD
or CBP, from the bundle or elsewhere, and no number derived from them sets anything in our pipeline (§4, "Where we drew
the compliance line"). What we model is how the published scoring formula behaves, using only Overture's own route
attributes, which is what any feature-based model of this target does implicitly. If the organisers rule otherwise, the
road features are separable: leaving them out of the feature list passed to `scripts/fit_linear.py` gives a road-free
model from the same probes.

**"Leaderboard probing is overfitting the public split."** Each probe returns one aggregate number for a whole feature,
never a tract; we have used 40 submissions up to 8 October (3 constants, 32 feature probes, 5 combinations; the full log is
`docs/probe_log.csv`), and the best-scoring model has 8 weights. We measured how much the public
split can mislead (`scripts/probe_noise.py`, `scripts/selection_noise.py`): differences between two submissions move by
about 0.0006 between public and private, and we choose the final pair with that in mind (`docs/final_selection.md`).
The optimism, the expected score being 0.004–0.007 better than observed for every combination that contained the unscaled facility probes, is reported, not hidden; §7 gives its cause.

**"The score is still far from 0, so the method does not work."** Scores of 0.0 on this leaderboard came from
reconstructing the target with the withdrawn layers, which the rules now forbid. Among label-free approaches the
comparison that matters is with constants under the same scorer: the best one we submitted scores 0.0977, the optimal
constant would score 0.0890 and all zeros 0.1072. Ours is 0.0634. (A formula-only estimator posted on 2 October reports
0.1028 next to an all-zero score of about 0.06; that all-zero figure is from the scorer used before 1–2 October, so the
two numbers cannot be placed on our scale.)

**"Why not train a model?"** There is nothing to train on: no labels were ever published, and the only supervision
available is one aggregate number per submission. The normal equations are the model that this supervision can
identify; anything with more parameters would be fitted to noise.

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
| lin_v6′ | lin_v5's features re-fitted on the re-probed values plus seven more (rural and facility flags, three road-shape terms); moments over the scored tracts | 0.0626 | **0.0634** |

The k grid (one probe each): correlation 0.610 at k = 1.0, 0.684 at 1.4, 0.683 at 2.0, so k = 1.4. Region slopes of the
composite differ (β 0.74 in south-central-tx, 1.10 in eastern-ok, 0.92 pooled), as the README's warning that road gaps
are not comparable across regions predicts; region interactions are also the most precise probes we have (subset SD of
the correlation about 0.01, against 0.045 for the road proxy and 0.08 for binary flags).

![Expected vs observed](figures/doc_expected_vs_observed.png)

The five combinations submitted up to 7 October scored worse than their point expectation (by 0.0039–0.0072), always in the same direction. The
blue line runs from the point expectation to the 90th percentile of 300 redrawn 30% splits (recomputed on 7 October
with every probe so far; the point values match those recorded before each submission). The grey boxes are the ranges
written down before submitting lin_v4 (missed) and lin_v5 (hit). The expectation uses full-set moments in
place of the hidden 30% subset and treats each probed covariance as exact, so it is optimistic by construction; we now
read the expectation as a ranking device and budget for that offset rather than adding features to close it.

**Region slopes of the composite** (scaled probes, 5 October; the fifth follows from the sum constraint
Σ_r composite×region_r = composite, so it costs no submission):

| region | slope β | how |
|---|---:|---|
| eastern-ok | 1.10 | probe |
| northern-ca | 0.81 | probe (a = 0.5) |
| south-central-tx | 0.74 | probe |
| maricopa-az | 0.63 | probe (a = 0.5) |
| eastern-wa | 0.14 | derived; few tracts, least certain |

The spread (0.6–1.1 among the four well-measured regions) is the README's warning that road gaps are not comparable
across regions, measured.

**What the scaled probes of 5 October showed.** A second road estimate that adds half of Overture's un-numbered
highway length to the reference (H2) correlates 0.596 with the target, below the main road estimate (0.684), yet adding it
to the combination lowers the expected RMSE from 0.0617 (the same model without H2) to 0.0596: the model uses the difference between the two
estimates, i.e. where un-numbered highways are long. Restricting the Farm-to-Market roads to tracts with no numbered
route scored −0.049 (±0.005): the reference evidently does not treat those roads as S1200. Whether the H2 contrast holds
on the leaderboard was tested on 6 October; it is accepted only if the public score improves by at least 0.0012.

**How we will choose the final two.** By our split simulation (`scripts/selection_noise.py`), the difference between two
submissions moves by about 0.0006 between the public and private parts, so a public gap under 0.0012 is not trusted.
That simulation assumes the 30% is drawn tract by tract; if the split is spatially grouped, as in another Zindi
geospatial challenge, the true spread is larger, so 0.0012 is a lower bound. The second pick is therefore not a shrunken
copy of the first (shrinking all weights and re-centring is a linear transform: its predictions correlate 1.0 with the
first and fail in the same places) but a model from a different feature family, with prediction correlation below 0.98
and expected RMSE within 0.003 (for example road features plus region slopes, without the facility flags: correlation
0.976 with lin_v3).

**Prediction written before submitting lin_v4 (5 October, 09:40 JST).** lin_v4 combines the k = 1.4 composite, both road
estimates, the five region slopes and the three facility features (11 weights); its expected RMSE is 0.0596. Adding the
optimism seen on all three earlier combinations (+0.0039 to +0.0048) predicts a public score of **0.0635–0.0644**, an
improvement of 0.003–0.004 over lin_v3 (0.0673). Two readings are fixed in advance:
- inside or below that range: the H2 contrast generalises at least to the public split, and lin_v4 becomes the first pick
  if it beats lin_v3 by 0.0012 or more (public 0.0661 or lower);
- above 0.0650: the optimism has grown with the number of weights, most likely through the contrast between two road
  estimates that correlate 0.94, and the model with fewer weights is kept.

**Outcome (6 October).** lin_v4 scored **0.0668**: outside the predicted range and above 0.0650. The optimism grew from
+0.004–0.005 to +0.0072, and the gain over lin_v3 (0.0005) is below the 0.0012 we trust. As fixed in advance, lin_v4 is
not adopted; the contrast between the two road estimates fitted the public split more than it generalised. We keep this
row because a pre-registered prediction that failed is the clearest evidence of how far the probe covariances can be
trusted once weights start to cancel.

**Why it failed, and what we changed.** If the probed covariances carry an error e (from substituting full-set moments
for the hidden public subset's), solving b = S⁻¹ĉ gives an actual public MSE equal to the expected MSE **plus 2bᵀe**. Large
weights of opposite sign amplify e. Redrawing the 30% subset 300 times (`scripts/robust_expected.py`), lin_v4's expected
RMSE spreads with SD 0.0065, against 0.0027 for lin_v3, and its observed 0.0668 sits at its 90th percentile (0.0671).
From 6 October we choose combinations by that 90th percentile, not by the point expectation. A combination that adds the
"fire station but no EMS place" flag had the best point expectation (0.0552) but an SD of 0.0086, with a weight of −0.13 on
a feature whose own correlation is +0.04: the same cancellation pattern, so it is not used.

**The offset that the simulation does not explain.** Every combination scored worse than its point expectation, by
+0.004 to +0.007. Even against the simulated spread, four of the five scored above their own 90th percentile (by 0.0011
to 0.0024), and the fifth, lin_v4, sits just below it (0.0668 against 0.0671; figure below). Under a random 30% split
each would land above its 90th percentile one time in ten. The five share one public split and overlapping features, so
they are not independent draws, but the same-sign offset across five feature sets points to a public split that is not
a simple random draw of tracts (other Zindi geospatial challenges have split by spatial grid). We treat the offset as an empirical
correction (+0.004 to +0.005) when predicting public scores, and we test the split directly: a region indicator
submitted at two scales gives two equations whose solution is the share of that region's tracts in the public part.

**The first combination chosen this way (7 October).** lin_v5 was picked by the 90th percentile and predicted, before
submitting, at 0.0657–0.0667 (point expectation plus the empirical offset). It scored **0.0664**, inside the range, and
its spread was smaller than lin_v3's (SD 0.0020 against 0.0027), because more of its covariances came from scaled probes.
Its gain over lin_v3 (0.0009) is still below the 0.0012 we trust, so both stay candidates for the final pair. Adding the
four facility and road-step probes of the same day would lower the 90th percentile by only 0.0007, so no further
combination was submitted.

**The offset explained (9 October).** Every combination submitted until then contained the same three facility
features, measured by unscaled probes in the first days. For "no fire place", a flag set on 71% of tracts, the
moment-substitution error of an unscaled probe is about ΔE[x]·(1/2 − E[y]) ≈ 0.0085 × 0.44 ≈ 0.0037, some 40% of its
covariance (−0.0086); five combinations sharing that one error would all miss in the same direction. We tested this in
one day: the facility-free model (no fire features) was predicted at 0.0673–0.0683 assuming the usual offset, and scored
**0.0652**, only +0.0019 from its point expectation; re-probing "no fire place" at a = 0.12 moved its correlation from
−0.211 to −0.060, and "fire station misfiled" from +0.072 to +0.145. With the re-probed values, and with moments over the
scored tracts only (eastern-wa confirmed unscored the same day, §6), lin_v5's offset shrinks from +0.0049 to +0.0026 and
the facility-free model's to +0.0011. A region indicator probed at two scales put south-central-tx at 0.6400 of the
public part, exactly its share of the scored tracts (6,003 of 9,379), so the spatial-split explanation we had kept open
found no support. The prediction for the facility-free model missed (it scored better than the range); we keep the miss
on record because it is what identified the cause. The remaining unscaled features (the road estimate, two region
interactions and the POI shortfall) are re-probed on 10 October.

**Where the facility-free model gained (9 October).** Both models are linear in the features, so the difference of
their MSEs can be written from probed quantities alone: E[p₁² − p₂²] − 2·E[(p₁ − p₂)y], where the second term is a
weighted sum of the probed E[xᵢy] (`scripts/why_alt_won.py`). With the re-probed values it predicts lin_v5 worse by
0.000191 in MSE; the observed gap is 0.000154. Group means read off the binary probes show where it comes from: lin_v5
predicted 0.089 for the 29% of tracts that have a fire place, against a probed mean of 0.068, and 0.048 for the rest
against 0.056. The old, unscaled probe had overstated how much "no fire place" lowers the gap, and that error alone
accounts for nearly all of the difference. By region the two models are equally biased (south-central-tx and the rest),
and on rural tracts lin_v5 was the more accurate one (0.112 against a probed 0.111; the facility-free model gives 0.102).
The facility features were not the problem; the measurement that set their weights was.

**The other unscaled probes held (10 October).** Re-probing the road estimate (a = 0.25), the two remaining region
interactions (a = 0.5) and the POI shortfall (a = 0.12) moved their correlations by −0.022, +0.001, +0.011 and −0.026,
all within the tolerance written down beforehand; only the two fire flags had been badly off. Re-fitted on the corrected
values, lin_v5's own feature set predicts almost the same as the facility-free model (correlation 0.990), so it can no
longer serve as the second, differently-wrong pick; the "no fire place" weight falls to about zero. A pre-registered
mechanism probe failed in the useful direction: tracts that are rural *and* outside metropolitan commuting areas (RUCA
7 or more) scored 0.03 below what the model predicts for them, not above it.

**lin_v6′ (11 October).** Re-fitted on the corrected values with moments over the scored tracts, lin_v5's feature set plus seven probed features was predicted at 0.0637–0.0653 and scored **0.0634**, 0.0008 from its point expectation: with the shared facility-probe error and the unscored region removed, the offset that had stood at +0.004 to +0.007 has all but gone. Two mechanism probes held the same day: small-city cores (RUCA 4 and 7) and tribal tracts without a fire place both have larger gaps than the model predicted (+0.061 and +0.029 over their nulls).

## 7a. After lin_v6′: looking for information, not form (12–22 October)

**One rule for every probe.** From 11 October each probe is judged against the value the current model already
implies. If the current model has weights b on features X, the probe of a new feature x is expected to return
cov(x, Xb) even if x carries nothing new; we call the corresponding correlation the *null*. A probe counts as
information only if |measured − null| > 0.015, a threshold fixed before the first such probe and never moved after
seeing a result. Before each probe we also write down the deviation it would need to lower the MSE by 2·10⁻⁴,
√(2·10⁻⁴ · share) / sd_y, where share is the fraction of var(x) the current features do not explain
(`scripts/null_probe_v2.py`). Every prediction, null and outcome is in `docs/probe_plan.md`, written before the result.

**What the probes found.** Region interactions of the road estimate: Texas −0.025 and eastern Oklahoma +0.021 from their
nulls (the road gap counts for less in Texas and more in Oklahoma than the pooled slope says); Arizona and California
within the threshold. Tertiary-heavy tracts +0.028; metropolitan core tracts (RUCA 1) −0.034; small-city cores
+0.061; tribal tracts without a fire place +0.029. Inside the threshold: land area, locally-calibrated k, the
road-positive flag by region, and three business-establishment proxies (one of them pre-registered as the stopping
rule for that family, which it triggered). Two more cleared the line on 16 October by a small margin (county-level k
+0.019, partial fire coverage +0.016), worth about 2·10⁻⁵ of MSE together. *Partial fire coverage* takes its form and its one constant from thread 35325: a tract with O ≥ 1 fire places may still have K ~ Poisson(u·λ) more stations in the reference, giving an expected fire gap K/(O + K), with u = 0.45 as published there. λ is our own Poisson fit of Overture fire places on population, land area, rurality and region; we did not tune u, and the feature's weight comes from our own probe.

**How strong is a hit?** Every deviation is measured on the public 30% (about 2,800 scored tracts) only. Its sampling
error is roughly √share · (RMSE / sd_y) / √n_public, so the fixed 0.015 line is seven standard errors for a region
interaction but only 1.5 for a 0/1 flag or a quantile bin, whose residual share is large. The four small hits of
16–17 October sit at 1.9–3.0σ after about thirty single probes, so some of them are probably the luck of the public
split. That does not change the public score of a combination fitted and scored on the same 30%, but it does mean we
do not count their public gain (about 3·10⁻⁵) as a private gain when choosing the final two (`scripts/judge_day.py`
prints the error next to every verdict).

**A ledger of road hypotheses** (`docs/road_hypotheses.md`). The reference length is about 1.4× our numbered-route
estimate, so roughly 30% of it is somewhere we do not see. Each candidate source was written down with a prediction
and a rejection rule before any data was aggregated:

| hypothesis | prediction written first | outcome |
|---|---|---|
| H1 un-numbered carriageway running parallel to a numbered one | correlation with the main estimate < 0.98 | 0.998: same information, rejected |
| H3 ramps counted in Overture's numerator (TIGER files ramps as S1630) | < 0.98 | 0.979, 3.5% new variance: small |
| H4 un-numbered highways from the import era (by source update time) | ≥ 1% of highway length | 45 km across five regions: rejected |
| H5 tertiary-or-lower segments whose *name* is a highway type (FM, state, county road) | ≥ 1% of highway length | Texas FM alone 7,557 km (6.5%); probe 18 October −0.002 from null (expected +0.074 if true): rejected |
| H6 tertiary segments signed at ≥ 45 mph (functional collectors) | ≥ 1%, correlation with H5 < 0.98 | 19% of highway length in Oklahoma and Washington, 4% elsewhere; correlation with H5 0.88; probe 18 October −0.011 from null (expected +0.114 if true, SE 0.005): rejected |
| H6-imp the same, with unsigned tertiary filled at the region's signed fast share | written after counting fill (below) | correlation with H6 0.83; would have shown +0.040 on the H6 probe: rejected by the same probe |
| H6′ segments of class `unknown` (removed from the shipped road file) with highway names | ≥ 1% | 10 km: rejected |

H6 treats a tertiary segment without a posted speed as slow. Counting how often the speed is posted at all
(`scripts/build_speed_fill.py`) showed that the low fast share outside Oklahoma is mostly missing tags, not slow
roads: speed limits cover 56% of tertiary length in eastern Oklahoma but 15–32% elsewhere, and among signed segments
25–67% are at ≥ 45 mph. We therefore wrote down, before the 18 October result, which variant follows a hit: a
deviation of +0.08 or more points to the raw H6 (expected +0.114 if it is true), a smaller hit to the filled-in
version (under which raw H6 would show only +0.040). The probe returned −0.011, below both: fast or named
tertiary roads are not where the missing reference length lies. With H1–H6 rejected, the 30% remains unexplained by
anything in the shipped Overture attributes, and we stopped spending submissions on road hypotheses.

**Is the gap a matter of model form?** Below the cluster of near-zero scores (reconstructions made before the
rule change), the best public scores were about 0.057 on 16 October against our 0.0634 (we do not know their methods), a difference of 7.4·10⁻⁴ in MSE. Before spending submissions on non-linear
combinations we bounded them. Taking a structural model of the scoring formula (minimum at 1, mean over defined
components; `scripts/expected_model.py`, refitted to all probes) as if it were the truth, the part of it that our
linear span cannot reach has variance 6.2·10⁻⁵. That bounds what piecewise recalibration, mixture forms (probability
a component is defined × its value), and separate fits by region or urbanity can add together: about one twelfth of
the gap. The remaining distance is information about *where* the reference length lies, not the shape of the
combination, so the remaining submissions went to H5/H6 and their follow-ups (pre-registered), with four quantile-bin
probes on 17 October as the one cheap test that could overturn this bound. It held: the two tail bins were within
0.01 of their nulls, and the two middle bins moved in opposite directions by 0.02 (predictions of 0.06–0.12 slightly
high, 0.12–0.20 slightly low), worth about 1.2·10⁻⁵ together. On 18 October both road hypotheses returned their
nulls (H6 −0.011 against +0.114 expected if true; H5 −0.002 against +0.074), which closes the road ledger.

**Facilities the places file misses (19–20 October).** With roads closed, the next candidate was the facility
term: tracts where the reference has a fire station or school but Overture *places* has none. Two probes tested it.
The first used only the places file (zero-facility tracts weighted by population, or by the expected station count
λ from a Poisson fit on population, land area, rurality and region); only the λ version moved (+0.018, 3.7 standard
errors, about 2·10⁻⁵ of MSE). The second used a different source inside the shipped data: Overture *buildings*
carry an OSM-derived class and name, so a building tagged `fire_station` or named “… Fire Station” marks a station
even when no place record exists (`scripts/build_bldg_facility.py`). Before probing we wrote down two rejection rules
(fewer than 1.5% of scored tracts affected; 80% or more of fire buildings already in tracts with a fire place); the
counts were 1.90% and 79.1%. Fire-zero tracts with a fire-station building (1.9% of scored tracts) returned +0.107
against a null of +0.025, 8.1 standard errors, the largest single hit since 12 October and about 9·10⁻⁵ of MSE.
The same test for schools gave +0.037 (2.8 standard errors, not counted), and extra fire buildings in tracts that
already have a station gave nothing. The combination built on 18 October (lin_b2y: the 25 features of 14 October,
partial fire coverage, the Texas county ratio and two prediction bins) scored 0.062708 public on 19 October, the
first replacement of lin_v6′; its point estimate was 0.0615, so the optimism of a combined fit has grown from 0.0008
to 0.0012–0.0014 as features were added.

A silent failure is worth recording. The feature builder clips every candidate to [0, 1]; the first population-
weighted facility features (log population, about 7–10) were clipped to 1 everywhere and became copies of the existing
zero-facility flag (three distinct values, correlation 0.87). The only symptom was an unusually small residual share in
the pre-registration table. We found it the evening before submission, rescaled the features, recorded the change
and the new nulls before any score came back, and made the builder warn whenever more than 1% of a feature is clipped.

**Closing the facility line (21–22 October).** Adding the fire-station building flag to lin_b2y gave lin_b2yf,
public 0.062055 on 21 October (point estimate 0.06069; the predicted range after the optimism correction was
0.0619–0.0621). The public gain over lin_b2y was 8.2·10⁻⁵ of MSE, about 80% of what the probe implied. Three
extensions of the building source were then probed against nulls written the evening before: extra school
buildings in tracts that have a school (−0.006, null), the fire-station flag restricted to rural tracts (−0.038,
3.4 standard errors *below* its null, so the building signal is weaker in rural tracts, not stronger) and EMS
buildings in EMS-zero tracts (+0.033, 2.5 standard errors, not counted). The one hit above three standard errors
would add 1.6·10⁻⁵ of MSE to lin_b2yf, under our 10⁻⁴ line for spending a submission, so it was not combined.
On 22 October we tested a different mechanism, coordinate offset at tract boundaries: the reference geocodes
stations by address while Overture places them on the building, so a station near a boundary could fall on
different sides in the two sources (`scripts/build_facility_near.py`). Fire-zero tracts with a station within
150 m outside the boundary returned +0.018 (1.4 standard errors); within 50 m, −0.002. We had written down that
an offset mechanism must be stronger at 50 m than at 150 m; it was the other way round, so the line is closed
and we do not claim the mechanism. Places listing a school only as an *alternate* category in school-zero tracts
returned +0.031 (2.6 standard errors), the same direction as school buildings on 20 October (2.8). Neither
reaches three standard errors, and we did not merge the two flags after seeing both results, because a merged
flag would re-read the same public rows and add no new evidence.

**Inventory of unused Overture attributes** (`docs/overture_columns.md`). The shipped road file is the unfiltered file
restricted by class; highway counts match exactly in all five regions, so no highway was dropped in packaging. Width is
never filled; surface is filled on 14% of highways; access rules, levels and destinations do not change length.
Place attributes (operating status, brand, contact fields, basic category) can only move the establishment half of the
facility term, where even a fully true hypothesis is worth at most 5·10⁻⁵. Building attributes are not pursued for
the building term itself, which is small (mean gap about 0.005); building *class and name* are used for the facility
term instead (the facilities paragraph above).

**Where the two final candidates disagree (7 October).** Without labels we cannot score the candidates region by region,
but we can say where their predictions differ, and therefore which kind of error the second pick insures against. We
compared lin_v5 with the facility-free model (road features, road-undefined flag and five region slopes; prediction
correlation 0.972). Their predictions differ by more than 0.02 on 18% of tracts. The difference is concentrated in
rural tracts in every region, and it has the same sign everywhere: lin_v5 predicts rural tracts about 0.01 higher.

| Region | Rural: mean difference / share above 0.02 | Urban: mean difference / share above 0.02 |
|---|---|---|
| eastern-ok | +0.0087 / 39% | −0.0053 / 15% |
| eastern-wa | +0.0078 / 27% | −0.0008 / 12% |
| maricopa-az | +0.0092 / 29% | −0.0017 / 12% |
| northern-ca | +0.0120 / 44% | −0.0004 / 14% |
| south-central-tx | +0.0100 / 37% | −0.0021 / 14% |

So the pair does not hedge one region against another. It hedges a single assumption: that the facility flags read
from Overture describe rural tracts correctly. If the private part holds a different share of rural tracts than the
public part, or if the facility signal measured on the public part does not carry over to rural tracts, the two picks
can swap order. In either case one of the two picks does not depend on that assumption.

The weights of the two candidates, from the same probes (`scripts/fit_linear.py`; region terms are slopes on the
composite within each region, eastern-wa derived from the sum constraint):

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

Without the facility flags, weight moves from the composite (which contains the facility terms) to the road estimate.

**The final two (chosen 21 October).** First: lin_b2yf (30 features: the 25 of 14 October, partial fire coverage,
the Texas county ratio, two prediction bins and the fire-station building flag; public 0.062055, also the best
90% point among the submitted combinations). Second: the facility-free model (seven features: composite, road
estimate, road-undefined flag and the region slopes; public 0.065236; prediction correlation 0.927 with the
first). A third candidate, the facility-free model plus the fire-station building flag, scored 0.064442, 0.0008
better than the facility-free model. We did not pick it. The gap is under our 0.0012 threshold. More importantly,
the fire-station flag is also in the first pick, so if that flag does not carry over to the private 70%, both
picks would move in the same direction; the second pick exists to insure against exactly the facility
assumption described above.

## 8. Reproduction

Code: https://github.com/IwataHiroki0827/bias-bounty-mapping-equity-writeup (public from the day this write-up is posted).
Data, submissions and credentials are not in the repository; every data step fetches from the challenge bucket.

One command after installing: `python scripts/reproduce_all.py` runs the steps below in order (skipping any whose
outputs exist) and checks the rebuilt submission against the SHA-256 recorded at submission time
(`docs/submitted_hashes.json`), since submitted files are not in the repository.

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

`docs/probe_log.csv` is the complete record of what the leaderboard told us: one public RMSE per probed feature
(plus the three constant calibrations hard-coded in `scripts/probe.py`). Nothing tract-level was ever returned or
stored. From that file and the feature tables, `reproduce_submission.py` re-derives every covariance, solves the weights
and writes the CSV. The log is in submission order and some features are probed again later at a smaller scale, so each
rebuild uses only the rows that existed when that combination was submitted (14 rows for lin_v3, 23 for lin_v5 and alt_nofac, 41 for lin_v6′ and 80 for lin_b2yf, the last two with moments over the scored tracts only); all five rebuilds match the submitted files' SHA-256.

**Tested from a clean clone** (2026-10-04): new virtual environment, `requirements.txt` only, all data fetched afresh,
DuckDB capped at 3 GB (`DUCKDB_MEMORY_LIMIT=3GB`), CPU only. The rebuilt CSV is identical to the submitted `lin_v3.csv`
(maximum difference 0.0 over 9,794 tracts); the feature tables take about 24 minutes. The test run found four gaps,
all fixed: a missing `matplotlib` requirement, a sample-submission file that had been placed by hand (now read from the
bucket), `features_all` being produced by a script whose name did not say so (now listed above), and Windows' path-length
limit breaking `pip` in a deep directory (use a short path such as `C:\bbr`).

**Tested again from a clean clone** (2026-10-25, after adding lin_b2yf): a fresh clone of the repository, a new
virtual environment, DuckDB capped at 2 GB, CPU only. All five rebuilds (lin_v3, lin_v5, alt_nofac, lin_v6′ and the
final pick lin_b2yf) match the SHA-256 recorded at submission, and both final picks are identical to the submitted
files (maximum difference 0.0 over 9,794 tracts). The whole run took about 29 minutes, with a peak of 1.95 GB of
memory. The test found one more gap, now fixed: the prediction-bin step read the private submission log
(`submissions/probes.jsonl`), which is not in the repository; it now rebuilds the same values from the public
`docs/probe_log.csv` (identical latest values for all 97 probed features).

Seeds: none of the steps is random except the noise bootstrap (seed 0). Versions are pinned in `requirements.txt`
(Python 3.12, DuckDB 1.5.6, pandas 2.2.3, NumPy 2.2.6, pyarrow 25.0.1, scikit-learn 1.6.1, SciPy 1.14.1, matplotlib 3.10.8).

## 9. Data, licences and attribution

- Overture Maps release 2026-08-19.0, as shipped in the challenge package: transportation and buildings under ODbL,
  places under CDLA-Permissive-2.0 (attribution: © OpenStreetMap contributors, Overture Maps Foundation).
- ACS 5-year housing units (B25001) and the strata tables, as shipped in the challenge package (US Census Bureau and the
  listed federal sources: public domain).
- USDA ERS RUCA 2020 (public domain), as shipped in the challenge package's strata; two flags from it enter lin_b2yf.
- No data from TIGER/Line, Microsoft Building Footprints, HIFLD or CBP is read anywhere in the scored pipeline.
