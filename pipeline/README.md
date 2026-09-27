# navigator_pipeline

Builds `SiteContext` (the facts about a site) from public data. Data is kept fresh two ways:

| How | What | When |
|---|---|---|
| **Scheduled refresh** | All 45 sources (map layers, zoning, hazards, sales, permits…) re-pulled from their APIs into a local store | Nightly check; each source re-downloads only when it has changed and its cadence is due |
| **Live lookups** | Fast-changing records for the parcel being analysed: assessment, tax liens, condemned status, city inventory, permits, and sales newer than the store (new comps) | Every report, in about 1–2 s |

Map layers change rarely and need heavy spatial queries, so they come from the refreshed store.
Every record in a SiteContext says where it came from: `provenance[...].retrieved` is `"live"`
or `"snapshot"`, with `retrieved_at`.

## Build a SiteContext

```python
from navigator_pipeline import site_context

ctx = site_context.build(["0052H00093000000"], live=True)   # report time
ctx = site_context.build(["0052H00093000000"], live=False)  # stored copy only, reproducible
```

`live=True` overlays live records on the stored copy. If a lookup fails or takes longer than
8 s, the stored value is kept and provenance says `"Live lookup failed (...); using the stored
copy from <date>"`. A report never fails because a source is down. Results are cached for an
hour per parcel.

Tables are loaded once per process (~2 s) and reloaded when the refresh rewrites them, so
later contexts take about 0.1 s. For the API: a `PipelineSiteSource` can call
`site_context.build(ids, live=True)` and validate the result with
`navigator_contracts.SiteContext`.

## Publish the results bundle

```bash
uv run python -m navigator_pipeline.publish               # Hazelwood + golden parcels -> results/
uv run python -m navigator_pipeline.publish --area Greenfield --out /tmp/greenfield
```

Scores every vacant lot in the area with the engine (from the stored copy, so it is
reproducible) and writes the small bundle the API and demo serve without the data store:
summaries, per-building-type CSV, analyses and contexts as gzipped JSON Lines, and simplified
EPSG:4326 geometry. About 90 s for Hazelwood; fails if the bundle exceeds 20 MB. Load it with
`navigator_pipeline.bundle.load()`; `pipeline/tests/test_results_bundle.py` checks it in CI.
Files and columns: `results/README.md`.

## Keep the store fresh

```bash
uv run python -m navigator_pipeline.refresh --dry-run   # what is due, what changed
uv run python -m navigator_pipeline.refresh             # do it
uv run python -m navigator_pipeline.refresh --force sales pli_permits
```

For each source past its cadence, the refresh asks the source when it last changed (WPRDC
resource date, ArcGIS last edit, latest council matter). If nothing changed it only records the
check. Otherwise it re-downloads (keeping the previous copy in `_previous/`, restored if the
download fails), rebuilds the clean tables that depend on it, and recomputes per-parcel facts
only if one of their inputs changed. Every run appends to `data/refresh_log.jsonl`.

| Cadence | Sources |
|---|---|
| Daily | sales, PLI permits, condemned properties, city-owned properties |
| Weekly | assessments, tax liens, council zoning legislation |
| Monthly | parcels, address points, zoning and overlays, hazard layers, FEMA, PA DEP, streets, transit |
| Yearly | HUD rents and overlays, URA Market Value Analysis |

**Cron** (nightly at 03:00; run from the repository root on the machine that holds the data):

```
0 3 * * * cd /path/to/aihorizons-housing && uv run python -m navigator_pipeline.refresh >> data/refresh.log 2>&1
```

## Data location

`data/` at the repository root, or `NAVIGATOR_DATA_DIR`. The store is not in git (only the
zoning code PDFs in `data/manual/zoning_code/` are, because the city's sites block automated
clients and they are downloaded by hand). Raw downloads also include owner mailing addresses
that cleaning removes. The repository ships the results bundle (`results/`) instead.

To get a store: extract the copy committed earlier (still in history, as of 2026-09-26) and
refresh it, or rebuild from scratch with `fetch`, `build`, `features` (about 30 minutes and
1.2 GB):

```bash
git archive 5552051 data/clean data/features data/raw | tar -x
uv run python -m navigator_pipeline.refresh   # fetches any raw input it needs
```

## Rules for outbound requests

Every request goes through `navigator_pipeline.http` with the identity `market-data-client/1.0`
and nothing else. No contact details, and no disguising the client to get past a block. Two
endpoints block this client and are therefore not used: the city's website (zoning board
decisions, zoning code) and WPRDC's SQL endpoint.

## Modules

`catalog` (sources and cadences) · `http` (the one client) · `fetch` (download + manifest) ·
`build` (clean tables) · `features` (per-parcel facts) · `site_context` (assembly) · `live`
(per-parcel lookups) · `refresh` (scheduled updates) · `publish` / `bundle` (results bundle) ·
`settings` (data location).
