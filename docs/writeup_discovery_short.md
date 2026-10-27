# Best Bias Discovery: whether a bus stop is on the open map depends on which agency runs the bus — Austin's network is 99% mapped, Houston's 15%

The full version, with every robustness check, is in the repository (`docs/writeup_discovery_draft.md`); this version keeps its section order.

> **In three lines.** Houston METRO's bus network is 15% on the open map and Austin's is 99%, in the same state and the same challenge region. Across 22 agencies, which agency runs the bus reaches pseudo-R² 0.363 for which stops are mapped, against 0.043 for every measure of need combined. 130,558 car-free households (at least 230,000 people) in Houston and San Antonio live where most stops are missing, and 5,729 of Houston's missing stops are in the region's most heat-exposed quarter of tracts.
>
> Nothing here is used to compute or calibrate any leaderboard submission.

## The finding in one paragraph

We matched every stop published by twenty-two transit agencies serving the five study regions (43,037 stops, from the agencies' own open GTFS feeds) against the Overture `infrastructure` and `places` layers of the challenge package (release 2026-08-19.0). Whether a stop exists on the open map is decided almost entirely by **which agency operates it**, and the spread is widest inside a single state and a single challenge region: in South-Central Texas, **Austin's Capital Metro is 99% mapped and Corpus Christi's RTA 93%, while Houston METRO is 15% mapped (7,491 of 8,797 stops missing) and San Antonio's VIA 17% (5,055 of 6,098 missing)**. The same split recurs in Northern California. In Eastern Washington, **Pahto Public Passage, the free public transit service the Yakama Nation runs, is 3% mapped: none of its 24 stops on the Yakama Reservation are on the map.** Within each operator, a higher share of households without a car does not make a stop more likely to be missing (if anything, the reverse). **130,558 car-free households in Houston and San Antonio, at least 230,567 people,** live in tracts where most of their bus stops are absent from the map.

## Why the automated scorecard cannot see this

The scored coverage gap has no transit term. Overture `infrastructure` is shipped in the package but is not part of any component, and the scorecard's strata (urban/rural, SVI, CVI, tribal, hazard) cannot express "which agency runs the service". The pattern also **reverses under the scorecard's own tribal stratum**: pooling stops by `tribal_any`, tribal tracts look *better* covered (91.4% vs 53.8% of stops mapped within 100 m), because all of Tulsa lies inside the Muscogee (Creek) and Cherokee reservations and Tulsa Transit is almost fully mapped. A tribal/non-tribal ratio therefore hides the one tribal transit system that is missing entirely. And a region-level average for South-Central Texas blends a 99% network with two at 15–17%. Eastern Washington, where the Yakama network sits, is in the package but not in the scored set at all: the challenge page lists the other four regions as the scored tracts, and a submission with 0.5 on its 415 tracts and 0 elsewhere scored exactly the same as all zeros (0.107246299). No number the scorecard produces reflects that region.

**The scorecard's own strata leave nothing behind.** Submitting 0/1 stratum flags alone and comparing each public score
with what our open-data estimate (public RMSE 0.062) predicts, no stratum departs by three standard errors except one
cell that failed its pre-registered check: SVI high/low −0.014/−0.020, tribal +0.005, wildfire top/bottom quarter
−0.021/+0.012, heat −0.018, summer/winter drought +0.015/+0.019, CVI top/bottom quarter +0.039 (3.0 SE)/−0.006 (0.5 SE,
so the CVI cell is not claimed), hazard × high SVI −0.021, rural/urban × high SVI −0.008/−0.011 (standard errors
0.007–0.013; 98 single-flag probes in total). The residual bias is not along the strata; it is along who supplied the data.

## Evidence

**Method.** For each GTFS stop (`location_type` 0) inside a tract of the challenge package, we compute the distance (EPSG:5070) to the nearest Overture `infrastructure` feature of class `bus_stop`, `bus_station`, `platform` or `stop_position`, and to the nearest Overture place whose category or name identifies a bus or transit facility. A stop counts as mapped if either lies within 100 m. Overture's `infrastructure` features, transit stops included, are derived from OpenStreetMap (Overture documentation, base theme, https://docs.overturemaps.org/guides/base/infrastructure/), so a stop missing here is missing from OpenStreetMap.

| Agency (region) | GTFS stops in package tracts | Mapped within 100 m |
|---|---:|---:|
| Tulsa Transit (eastern-ok) | 1,191 | 99.6% |
| Capital Metro, Austin (south-central-tx) | 2,336 | 99.1% |
| Roseville Transit (northern-ca) | 193 | 99.0% |
| Yuba-Sutter Transit (northern-ca) | 289 | 96.5% |
| Corpus Christi RTA (south-central-tx) | 1,407 | 92.5% |
| Ben Franklin Transit (eastern-wa) | 876 | 92.2% |
| Spokane Transit (eastern-wa) | 1,639 | 91.0% |
| Sacramento Regional Transit (northern-ca) | 1,748 | 90.2% |
| El Dorado Transit (northern-ca) | 50 | 90.0% |
| Redding Area Bus Authority (northern-ca) | 309 | 85.4% |
| Valley Metro (maricopa-az) | 8,021 | 83.5% |
| TRAX, Tehama County (northern-ca) | 107 | 78.5% |
| Unitrans, Davis (northern-ca) | 32 | 62.5% |
| DART, Dallas (south-central-tx) | 6,976 | 54.8% |
| Yakima Transit (eastern-wa) | 634 | 54.3% |
| Trinity Metro, Fort Worth (south-central-tx) | 1,573 | 45.1% |
| B-Line, Chico (northern-ca) | 483 | 25.1% |
| People for People, rural routes (eastern-wa) | 94 | 24.5% |
| **VIA Metropolitan Transit, San Antonio (south-central-tx)** | **6,098** | **17.1%** |
| Placer County Transit (northern-ca) | 151 | 16.6% |
| **METRO, Houston (south-central-tx)** | **8,797** | **14.8%** |
| **Pahto Public Passage, Yakama Nation (eastern-wa)** | **33** | **3.0%** |

![Coverage by agency](figures/transit_coverage_by_agency.png)

**It is not a matching artefact.**
- The radius does not matter. Overture `infrastructure` alone at 25 / 50 / 100 / 200 m: Houston 5.5% / 6.8% / 8.8% / 12.2%, Austin 94.4% / 97.6% / 99.1% / 99.6%; Pahto is 3.0% at every radius.
- The gap is already there upstream. OpenStreetMap holds **680** `highway=bus_stop` nodes in all of Harris County, against 8,797 stops on METRO's own feed. Overture is faithfully carrying what OpenStreetMap has; the missing networks were never added to OpenStreetMap (queries in `docs/overpass_queries.md`).
- **How the mapped networks got there.** Each Overture transit feature carries the time of its last edit. In each well-mapped city, most features share one year, the signature of a bulk import or a bulk clean-up: Travis (Austin) 2,108 of 2,325 in 2025; Nueces (Corpus Christi) 1,192 of 1,267 in 2020. Harris (Houston) and Bexar (San Antonio) have no such year: their 829 and 788 features are spread thinly over 2009–2026. The networks on the map are the ones someone loaded as a whole.

  ![Edit year by county](figures/transit_edit_year.png)
- The low networks are ordinary fixed-route systems (no GTFS booking rules; under 2% of stop-times require a call), not demand-response zones; Pahto is also fixed-route.

**Agency, not need, explains which stops are missing.** A stop-level logistic regression (42,854 stops with tract SVI and car-free share):

| model | predictors | McFadden pseudo-R² | AUC |
|---|---|---:|---:|
| need only | car-free household share, SVI, rural, tribal | 0.043 | 0.637 |
| agency only | 22 operator indicators | 0.363 | 0.868 |
| agency + need | both | 0.374 | 0.879 |

The outcome is 1 if the stop is mapped. Adding need on top of the operator moves pseudo-R² by 0.011. Within an operator, a higher car-free share slightly *raises* the odds of a stop being mapped (+2.91 log-odds per unit share) and a higher SVI lowers them (−1.19 per unit). Houston METRO's service tracts have the highest car-free share of the large networks (9.5% of households) and the lowest coverage. In Houston tract 48201312400, 28 stops are 4% mapped and 485 households (47.1%) have no car; in San Antonio tract 48029141000, 21 stops are 0% mapped and 506 households (38.9%) have no car. 653 of the 716 tracts with METRO stops, and 269 of the 300 tracts with VIA stops, are majority-unmapped. On the Yakama Reservation, 10 of the 11 tracts with Pahto stops have no mapped stop at all.

## Who is affected and why it matters

- **Scale.** 89,960 car-free households in Houston and 40,598 in San Antonio live in tracts where most of their stops are missing; with Dallas and Fort Worth, 166,048 in South-Central Texas. Counted as people, that is at least 161,300 in Houston, 69,267 in San Antonio and 291,878 across the four networks (ACS table B08201 gives car-free households by household size; households of four or more are counted as four, so these are lower bounds).
- **Heat and climate vulnerability, from the challenge's own strata.** South-Central Texas is one of the challenge's heat regions, and the missing stops sit where the risk is highest. Of Houston METRO's 7,491 unmapped stops, **5,729 are in tracts in the region's top quarter for dangerous-heat days** (`gehe_wbgt30_days_mean`, WBGT above 30 °C) and **4,848 in the top quarter of the Climate Vulnerability Index** (`cvi_overall`); for San Antonio VIA, 2,588 unmapped stops are in top-quarter CVI tracts. Of Austin's stops, which are on the map, none are in top-quarter heat tracts and 1.8% in top-quarter CVI tracts. For households without a car, reaching a cooling centre or clinic during a heat event depends on the bus.
- **What a "nearest bus stop" query returns.** For a rider standing at a Houston METRO stop, the nearest transit feature on the open map is a median **386 m** away (Austin: 2.5 m); for 845 stops there is nothing within 1 km. In San Antonio the median is 473 m and 906 stops have nothing within 1 km.
- **Named destinations are missing too.** Among Houston METRO's stops named after a hospital or clinic, 7 of 12 are absent from the map, among them `LBJ Hospital` (Harris Health's public safety-net hospital), `VA Hospital` and `MLK Clinic`; 6 of its 6 stops named after a school are absent. For San Antonio VIA it is 4 of 8 medical stops (among them `Eckhert at the Frank Tejeda VA Clinic`) and 18 of 22 school stops (`HEIMER IN FRONT OF COKER ELEM. SCHOOL`). Austin's 2 medical and 11 school stops are all mapped. The counts are small, and taken together these stops are not missed more often than the agency's other stops; the point is what a missing stop is in practice (`scripts/transit_destinations.py`).
- **Evacuation and relief.** Houston is a hurricane evacuation city, and residents without a car depend on public transport to leave or to reach a shelter. Coverage maps and walk-time isochrones built on this base map understate their access.
- **Tribal health access.** Pahto connects reservation communities to the Yakama IHS clinic, the Yakima Valley Farm Workers clinic in Toppenish and Heritage University. An agency that relies on the open map for emergency transport planning on the reservation cannot see the network the Nation itself operates.

## Recommendation

1. Treat transit-stop coverage as a separate component, measured against the agency's own GTFS, not against population or density proxies.
2. For METRO, VIA and Pahto, the fix is an import, not a survey: all three publish open GTFS feeds. A licence-checked import of stop locations into OpenStreetMap, following its import guidelines, would flow into Overture's next release. Austin and Corpus Christi show that the same state reaches 93–99% once that import has happened.
3. Report coverage per operator, not only by pooled strata.

What an import would add, per agency below 60% (stops in package tracts with no Overture transit feature within 100 m):

| Agency | Stops missing from the map | Coverage today |
|---|---:|---:|
| METRO, Houston | 7,491 | 14.8% |
| VIA, San Antonio | 5,055 | 17.1% |
| DART, Dallas | 3,155 | 54.8% |
| Trinity Metro, Fort Worth | 863 | 45.1% |
| B-Line, Chico | 362 | 25.1% |
| Yakima Transit | 290 | 54.3% |
| Placer County Transit | 126 | 16.6% |
| People for People | 71 | 24.5% |
| Pahto Public Passage (Yakama Nation) | 32 | 3.0% |
| **Total** | **17,445** | |

The data to close the gap already belongs to the agencies and, for Pahto, to the Yakama Nation itself; the decision to publish it into OpenStreetMap, and how, is theirs.

## Reproducibility

Code: https://github.com/IwataHiroki0827/bias-bounty-mapping-equity-writeup (public from the day this write-up is posted). GTFS feeds are the agencies' open data; source URLs and retrieval dates per feed are in `data/raw/ext/gtfs/sources.json`.

**One command:** `python scripts/reproduce_discovery.py` downloads what is missing, rebuilds every table and then recomputes the 58 headline numbers of this write-up (stop counts and coverage per agency, county bus-stop counts, car-free households and people, stops named after hospitals and schools, the three pseudo-R² values, the edit-year bursts, the climate-risk counts, the nearest-stop distances) and checks each against the value printed here (50 checks at the time of the 7 October clean run, 58 now): `PASS` / `FAIL`, exit code 0 only if all match. The GTFS files' SHA-256 are recorded in `docs/discovery_manifest.json`; if an agency has since published a new feed, the check says so, so a drifted number can be told apart from a broken pipeline. This has already happened once: a run from a fresh clone and environment on 7 October passed 48 of the 50 checks and reported that three agencies had published new feeds; the two misses were Redding's coverage, whose new feed has 268 stops instead of 309 (88% mapped instead of 85%), and the tribal / non-tribal rate that includes it (0.537 instead of 0.538). No conclusion changes. A second run, from a fresh clone of the public repository on 27 October, passed 45 of the 58 checks: ten of the 22 feeds had been republished since retrieval, every miss traces to one of those ten, and the twelve unchanged feeds reproduce every number exactly. The largest moves are Houston METRO (8,803 stops instead of 8,797, still 15% mapped; 90,075 car-free households in majority-missing tracts instead of 89,960) and Redding (256 stops, 90% mapped). No conclusion changes; that run took about four minutes. Tested with Python 3.12, DuckDB 1.5.6, pandas 2.2.3, scikit-learn 1.6.1, SciPy 1.14.1 (pinned in `requirements.txt`); CPU only, about 15 minutes, most of it remote DuckDB reads.

Challenge data is read remotely from Source Cooperative with DuckDB. Additional public data (Best Bias Discovery only), retrieved 2026-10-02 to 2026-10-05: GTFS feeds via the Mobility Database catalogue (`https://files.mobilitydatabase.org/feeds_v2.csv`) and the agencies' own URLs; ACS 2020–2024 5-year table B08201, file `acsdt5y2024-b08201.dat` from www2.census.gov.

## Objections we anticipated

**"Transit is not part of the coverage gap, so this is out of scope."** A tract in Houston with a 0% mapped bus network can score a coverage gap of 0. A bias the metric is blind to is the kind the bounty asks for.

**"Missing stops do not stop anyone riding the bus."** Riders do not need the map; planners, relief agencies and routing tools do.

**"Everyone in OpenStreetMap knows imports matter."** That an agency's data decides whether its stops reach OpenStreetMap has precedents: in Florida in 2010–11, four agencies' stops were uploaded while Sarasota's could not be, because of problems in its GTFS file and staff turnover (https://wiki.openstreetmap.org/wiki/FL_Bus_Stops). What we did not find in prior work is the test that coverage is unrelated to need; the audits of open map data we found concern buildings, against wealth, population density and urban/rural share (Gevaert, Buunk and van den Homberg, IEEE JSTARS 17, 2024, four building datasets including Overture and OpenStreetMap). What the challenge's tooling cannot show is the size (99% vs 15% in one region), that it follows the operator and not need, and that the unloaded networks belong to the fourth- and seventh-largest US cities. Our contribution, beside threads 34972 and 35154, is the transit case, with the supplier identified for 22 networks and the mechanism dated from Overture's own edit history.

**"The heat numbers just reflect Houston's climate."** Partly: the most heat-exposed large city is the one whose stops the map lacks.

**"The edit-year bursts could be a later bot or clean-up, not an import."** Possible: last-edit time is not creation time. But OpenStreetMap holds 680 bus stops in all of Harris County against 8,797 on METRO's feed, while Travis County holds 2,279 against Capital Metro's 2,336.

**"A 100 m radius is generous."** It can only inflate coverage, never hide it. The low networks stay low at every radius (`infrastructure` alone: Houston 5.5% at 25 m to 12.2% at 200 m).

**"Car-free households are not people."** Correct; ACS B08201 counts households. Our people counts treat households of four or more as four, so they are lower bounds.

## Limitations

- GTFS is the agency's own record, not ground truth; a few stops may be seasonal or temporarily closed. Three feeds do not cover October 2026 (TRAX, Corpus Christi RTA, Sacramento RT); all three are high-coverage, so they do not drive the finding.
- GTFS feeds contain errors: 21% of 632 US feeds had at least one validator error, the most common in route-shape distances (Devunuri and Lehe, *Findings*, 2024, https://findingspress.org/article/116694-a-survey-of-errors-in-gtfs-static-feeds-from-the-united-states).
- Licences. US agencies publish GTFS under a mix of open licences, agency terms and no stated terms; every feed here is a public download without registration, and the repository downloads them rather than redistributing them. The terms we found are listed per feed in `docs/gtfs_licenses.md`. The conclusion does not rest on the feeds without stated terms: on the seven feeds with stated terms (METRO, VIA, Capital Metro, Valley Metro, Corpus Christi RTA, Sacramento RT, Roseville; 28,453 stops) the operator reaches pseudo-R² 0.440 against 0.030 for need, and without VIA, whose terms limit use to helping riders or promoting public transport, 0.453 against 0.018. Attribution as the agencies require: Data is provided by permission of The Metropolitan Transit Authority of Harris County, Texas. Data provided by VIA Metropolitan Transit. Data provided by Trinity Metro is not warranted by Trinity Metro for accuracy or completeness and data is subject to change without notice.
- We count a stop as mapped if any Overture transit feature lies within 100 m; this can only overstate coverage.
- Operator: Pahto Public Passage is provided by the Yakama Nation (Yakama Nation Tribal Transit, created in 2007 under the Nation's Economic Development programme; https://www.pahtotransit.com/contact.php, https://yakamaecondev.com/pahto-transit/, retrieved 2026-10-02).
- Only agencies with an open GTFS feed are covered. Eastern Oklahoma's tribal transit programmes publish no feed we could find, so the tribal comparison rests on one Nation's service.
