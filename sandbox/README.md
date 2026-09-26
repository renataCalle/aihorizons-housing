# sandbox

The research scientist's working copy of the real data behind the Navigator: every
source from the spec, pulled with provenance, cleaned into analysis-ready tables, and
rolled up into per-parcel facts shaped like `SiteContext`.

This folder is for research: prototyping engine modules, choosing golden parcels, and
calibrating thresholds. It is not the production pipeline (that is `pipeline/`, owned by the
engineer). Nothing in `engine/`, `pipeline/`, or `api/` may import it.

## Try it: parcel in, report out

```bash
uv run python -m sandbox.navigator 4-A-303                       # block-lot
uv run python -m sandbox.navigator 0052H00093000000              # county id
uv run python -m sandbox.navigator "5607 ELMER ST"               # address
uv run python -m sandbox.navigator 52-H-93 --set hard_cost_psf=200 --land-price 150000
```

Runs the v0 engine (`engine_v0/`: rules engine -> constraint flags -> entitlement odds ->
pro forma Monte Carlo -> score -> next steps) and writes the full JSON to
`sandbox/data/output/<parcel_id>.json`. Every non-data number lives in
`engine_v0/assumptions.py` (and the flag table in `engine_v0/constraints.py`), marked
PLACEHOLDER until replaced by local benchmarks or calibration; the report lists them.

## Run it

```bash
uv sync
uv run python -m sandbox.fetch                 # ~1.3 GB raw, about 10 minutes
uv run python -m sandbox.build                 # clean tables, about 10 minutes
uv run python -m sandbox.features              # per-parcel facts, City of Pittsburgh
uv run python -m sandbox.features --county     # same, all 585k county parcels
uv run python -m sandbox.site_context 12-A-34  # SiteContext JSON for a parcel or assemblage
```

Manual downloads (sites that block this client) go in `sandbox/data/manual/`. From the
zoning code PDFs saved there, a draft rules table is generated for review:

```bash
uv run python -m sandbox.rules.extract         # -> sandbox/rules/residential_draft.csv
```

Each row has the district, standard, value, code section, effective date, source page, and
the verbatim source line. `reviewed_by` stays empty until a person checks the row against
the PDF, per the spec. Rows with district `*` record standards that are resolved elsewhere,
absent from Pittsburgh's code, or still missing.

Two companion drafts were read by hand from the 254-page Title Nine download
(`sandbox/data/zoning_code/`), because their tables do not survive text extraction:

- `rules/use_permissions_draft.csv`: which residential product types each district allows
  (P / A / S / C) from the 911.02 use table, read from the page image.
- `rules/standards_draft.csv`: parking minimums and reductions (914), Hillside conditions
  (911.04.A.69), grading and retaining-wall limits (915.02), ADU overlay (912.08).

Golden parcels and the rules engine prototype:

```bash
uv run python -m sandbox.golden --export              # pick 8 golden parcels -> fixtures/golden/site_context/
uv run python -m sandbox.engine_v0.rules_engine       # envelope + relief check on each fixture
```

`golden.py` encodes each spec case as a filter that isolates one condition (the picks are in
`golden_parcels.json`). `engine_v0/rules_engine.py` reads only a fixture and the rules CSVs:
strict envelope from the district table, a contextual envelope (925.06.C, 3 ft sides) when
both neighbors are built, the 911.04.A.69A townhome width rule, 925.01.C undersized lots,
and the UM-O / FP-O overlay procedures. Product templates and the 25% dimensional-variance
cap are labeled assumptions.

`--ids` on `features.py` computes facts for specific parcels (e.g. outside the city) without
a county run.

Each step skips work already done. `fetch --force <key>` re-downloads a source, and
`build <name>` rebuilds one table. Data lives in `sandbox/data/`, which git ignores.

```
sandbox/data/
  raw/<key>/          immutable downloads + _manifest.json (url, source as-of, sha256)
  clean/<name>.parquet  one table per layer, EPSG:2272 (State Plane South, US ft)
  features/           parcel_facts, parcel_zoning, parcel_flood, parcel_env_nearby
```

## Conventions

- **Geometry:** PA State Plane South, US survey feet (EPSG:2272), so areas are in square feet.
- **Parcel key:** `parcel_id` is the 16-character county id (e.g. `0001B00024000000`).
  `block_lot` is the dashed city form (`1-B-24`). `site_context` accepts either.
- **Facts only in `features/`:** shares of lot area (0–1), distances in feet, counts.
  No severities, costs or thresholds.
- **Null means unknown, never zero:** a layer that covers only the city gives null for
  suburban parcels, with the reason in `coverage_note`.
- **Personal data dropped:** owner mailing addresses (assessments), owner names (permits,
  condemned properties) and tank-owner addresses are not carried into clean tables.
- **Outbound identity:** every request sends `User-Agent: market-data-client/1.0` and
  nothing else. Never add contact details to it.

## Sources

`catalog.py` is the source of truth. Grouped by the spec's waves:

| Wave | Layer (clean table) | Source | Notes |
| --- | --- | --- | --- |
| 1 | `parcels` | WPRDC parcel boundaries (Sep 2026) + property assessments | 585k parcels, 99.8% matched to an assessment |
| 1 | `address_points` | County address points | 661k points, linked to parcel ids |
| 1 | `municipalities`, `neighborhoods` | WPRDC | Neighborhoods are city only |
| 2 | `zoning` | City zoning districts | 57 district codes |
| 2 | `historic_districts`, `historic_sites`, `greenways`, `parks`, `height_overlay`, `parking_reduction_overlay`, `riverfront_overlay`, `uptown_ipod` | WPRDC | City overlays |
| 2 | `steep_slope`, `landslide_prone`, `undermined` | WPRDC environment group | **City only** |
| 2 | `landslides_observed` | WPRDC landslide inventory | Points |
| 3 | `fema_flood_zones` | FEMA NFHL (current, DFIRM 42003C) | Simplified to ~1 m server-side; floodway and 0.2% zones split out |
| 3 | `dep_land_recycling` | PA DEP eMapPA, land recycling (Act 2) cleanup sites | Deduplicated across media; media listed per site |
| 3 | `dep_storage_tanks` | PA DEP storage tanks, active + inactive | |
| 3 | `dep_aml`, `dep_digitized_mined_area` | PA DEP abandoned mine lands; digitized deep-mined areas | **Countywide undermining**, beyond the city-only layer |
| 3 | `combined_sewershed` | PWSA via WPRDC | Proxy; pipe capacity is not public |
| 3 | `water_providers` | WPRDC providers by parcel | Covers 199k of 585k parcels |
| 3 | `street_centerlines`, `city_steps` | County centerlines (Census feature class) + City Steps | Frontage classes: street, alley, steps, walkway, private drive |
| 3 | `sales` | County sale transactions 2012–2026 | 504k records; `arms_length` flags valid and new-build sales |
| 3 | `hud_safmr`, `hud_fmr_metro` | HUD Small Area FMR by ZIP; metro FMR | Rent benchmarks by bedroom |
| 3 | `market_value_analysis` | URA Market Value Analysis 2021 | Market type per block group |
| 4 | `council_zoning_matters` | Pittsburgh City Council via Legistar API | 735 zoning items 2000–2026: conditional uses, map amendments, PUD/SP, code text, with durations |
| 4 | `pli_permits` | PLI permits (OneStopPGH) | 65k permits since Jun 2019; new construction / demolition flags |
| 4 | `condemned` | Condemned and dead-end properties | |
| 4 | `transit_stops` | PRT stops with weekday trips per stop | Frequent transit tiers: any, ≥32, ≥64 weekday trips |
| 5 | `city_owned` | City-owned property inventory | 12.5k parcels; Land Bank and URA pending transfers |
| 5 | `tax_liens` | County tax lien summary | 88k parcels with liens |
| 5 | `hud_qct`, `hud_dda`, `opportunity_zones` | HUD | LIHTC and Opportunity Zone overlays |

The GTFS feed (`raw/gtfs`) is downloaded but not needed yet: PRT's stop file already
carries weekday trip counts.

## Gaps

Each gap comes with what is used in its place.

| Spec need | Status | Workaround |
| --- | --- | --- |
| **Zoning Board of Adjustment decisions** (entitlement model) | **Blocked.** pittsburghpa.gov returns HTTP 403 to this client for every page, including robots.txt. | Council conditional uses and rezonings from Legistar give approval rates and filing-to-decision durations for the council path. ZBA cases need another route (see open questions). |
| Permit review time (months to permit-ready) | PLI permits carry an issue date only, no application date | Usable for by-right validation (what got built, where); review time needs another source |
| Countywide steep slope and landslide-prone areas | WPRDC layers cover the city only | Statewide LiDAR (spec wave 5 stretch) |
| ACS rents and values | The Census API now requires a key, and a key requires an email sign-up | HUD SAFMR by ZIP for rents; county sales for values |
| Pittsburgh Land Bank holdings | No standalone dataset found | City inventory rows marked "PLB Transfer"; URA via land use "Municipal Urban Renewal" |
| Parcel frontage length (`frontage_ft`) | Not computed | `frontage_type` is from distance to classified centerlines (≤60 ft) |
| ZBA cases near a parcel (`zba_cases_nearby`) | Null with reason in provenance | Depends on the ZBA source |

## Open questions for the team

1. **ZBA data.** Options: ask City Planning for a bulk export of ZBA decisions; request an
   allowlist for the `market-data-client/1.0` agent; or find a mirror (the ZBA agendas
   are also posted to the city's public-notice channels). Changing the user agent to get
   past the block is not an option under our outbound-request rule.
2. **Census API key.** Needed only if ACS is wanted beyond HUD rents. It requires an email
   sign-up, so it needs the research scientist's decision on which address to use.
