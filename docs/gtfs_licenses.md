# GTFS feed licences and terms (checked 2026-10-10)

The Best Bias Discovery rules ask that additional sources be "publicly accessible, openly licensed, documented with URLs
and retrieval dates, and reproducible by the judges". US transit agencies publish GTFS under a mix of open licences,
agency-specific terms and no stated terms. This table records what each agency says. All 22 feeds are downloadable
without registration. The repository does not redistribute any raw feed: `scripts/discovery_transit.py` downloads each
one from the URL in `FEEDS`, and only derived counts and rates are published.

"Verified" means the terms page was opened on 2026-10-10 and the quoted wording read; the other rows rest on the Mobility
Database catalogue (feeds_v2.csv, retrieved 2026-10-10) or a search result and are marked as such.

| Agency (feed) | Terms | Reuse / redistribution | Attribution required | Status |
|---|---|---|---|---|
| METRO Houston | METRO Data Use Agreement, https://www.ridemetro.org/about/news-media/digital-assets | "reproduce, redistribute, incorporate for personal or commercial use, and publicly display the Data"; no purpose limit | "Data is provided by permission of The Metropolitan Transit Authority of Harris County, Texas." | verified |
| VIA Metropolitan Transit (San Antonio) | VIA Developer's License Agreement, https://www.viainfo.net/developers/ | "non-exclusive, limited, and revocable rights to use, reproduce, and redistribute", limited to uses "assisting mass transportation riders or in furtherance of promoting public transportation" | "Data provided by VIA Metropolitan Transit" | verified; purpose-limited |
| Capital Metro (Austin) | https://www.capmetro.org/metrolabs/ | "non-exclusive, limited and revocable rights to use, reproduce, and redistribute" (as reported) | credit CapMetro | search/agent report |
| Valley Metro (Phoenix) | ODC-BY (catalogue) | open licence with attribution | credit Valley Metro | catalogue |
| Corpus Christi RTA | CC BY 4.0 reported on https://www.ccrta.org/gtfs (catalogue: none) | open licence with attribution | credit CCRTA | to re-check |
| Sacramento RT, Roseville | SacRT transit data licence (catalogue link https://www.sacrt.com/gtfs/) | revocable rights to use, reproduce, redistribute (as reported) | credit SacRT | search/agent report |
| DART (Dallas) | catalogue link no longer resolves; current legal notices page has a general disclaimer only | not stated | — | no stated licence |
| Trinity Metro (Fort Worth) | https://ridetrinitymetro.org/gtfs-data/ | not stated; public use must display a disclaimer | "Data provided by Trinity Metro is not warranted by Trinity Metro for accuracy or completeness and data is subject to change without notice." | agent report |
| Unitrans (Davis), RABA (Redding) | agency pages in the catalogue (https://unitrans.ucdavis.edu/about/gtfs/, rabaride.com) | not read | — | to check |
| Tulsa Transit, Spokane Transit, Ben Franklin, Yakima Transit, People for People, Pahto Public Passage (Trillium-hosted), Yuba-Sutter, Placer County, El Dorado, TRAX, B-Line (NTD entry) | none found | not stated | — | no stated licence |

## What depends on which feeds

- The headline contrast (Houston METRO 15% against Capital Metro 99%, same state and region) uses METRO (permissive
  agreement with attribution, verified) and Capital Metro (permissive but revocable, as reported).
- San Antonio VIA's terms limit use to helping riders or promoting public transport. This analysis exists to get VIA's
  stops onto the open map that riders' apps use, which we read as within that purpose, but it is VIA's term, not an
  open licence; every VIA number can be dropped without changing the conclusion (Houston and Austin carry it).
- Feeds without stated terms (including Tulsa and Pahto) are public downloads from the agency or its host. If the judges
  read "openly licensed" strictly, the pseudo-R² comparison can be recomputed on the subset with stated permissive or
  open terms. Done on 2026-10-10: on the seven feeds with stated terms (METRO, VIA, Capital Metro, Valley Metro, CCRTA,
  SacRT, Roseville; 28,453 stops) the operator reaches pseudo-R² 0.440 against 0.030 for need; without VIA (six feeds,
  22,362 stops) 0.453 against 0.018. All 22 feeds: 0.363 against 0.043. The conclusion does not depend on the feeds
  without stated terms.

## Required attribution notices (to be printed in the write-up and README)

- Data is provided by permission of The Metropolitan Transit Authority of Harris County, Texas.
- Data provided by VIA Metropolitan Transit.
- Data provided by Trinity Metro is not warranted by Trinity Metro for accuracy or completeness and data is subject to
  change without notice.
- GTFS data from Valley Metro (ODC-BY), Capital Metro, Sacramento Regional Transit, Corpus Christi RTA and the other
  agencies listed above; Mobility Database mirror (https://mobilitydatabase.org) for feeds whose official URL refused
  automated download.
