# 06 · Mock data

Goal: every screen works and looks like the mockups before the pipeline and engine are ready, and the switch to real data changes nothing above the API's `SiteSource`.

## Three stages

1. **Now (no engine yet):** `MockSiteSource` serves the UI-draft fixtures in `fixtures/mock/ui-draft/` plus generated parcels, as prebuilt summaries and analyses. Everything is marked illustrative. This unblocks the whole UI.
2. **Engine ready:** the mock only provides **facts** (SiteContext) and geometry. Summaries and analyses come from `navigator_engine`, so scores are real engine output on fake facts. Delete the prebuilt analyses.
3. **Pipeline ready:** `SITE_SOURCE=pipeline`. SiteContext comes from the pipeline for real parcels. The teammate's golden parcels in `fixtures/golden/` become the demo set.

Build stage 1 so that stage 2 only swaps where analyses come from.

## Golden vs. mock

- `fixtures/golden/` belongs to the teammate: real Pittsburgh parcels, paired `site_context/` and `site_analysis/`, used as snapshot tests. **Don't put fake data there.**
- `fixtures/mock/` is for illustrative data: `ui-draft/` (the hand-made fixtures that match the mockups) and `generated/` (the generator's output, gitignored if large).

## Generator

`api/scripts/generate_mock_sites.py` (pyproj as a dev dependency of the API, or ask the teammate to host it in `pipeline/`). Fixed random seed, so screenshots are reproducible. Output in `fixtures/mock/generated/`:
- `site_context/{parcel_id}.json`: valid SiteContext (facts only, EPSG:2272 geometry, overlay facts as 0–1 shares, missing facts null with a provenance reason)
- `parcels.geojson`: EPSG:4326 for the map
- stage 1 only: `summaries.json` and `site_analysis/{parcel_id}.json`, from the mock scoring below

## Geography

Synthetic lots in slightly rotated street-grid blocks around real neighborhood centers:

| Neighborhood | Approx. center (lon, lat) | Lots |
|---|---|---|
| Hazelwood | −79.943, 40.405 | 120 |
| Greenfield | −79.938, 40.423 | 90 |
| Glen Hazel | −79.927, 40.398 | 60 |
| Outside the city (Mt. Lebanon) | −80.049, 40.373 | 5 |

Lots are roughly 28 × 60 ft to 40 × 125 ft, in blocks of 2 rows by 7 lots with street gaps. About 15% are candidates (vacant or underused); the rest are "not a candidate".

## IDs and names

Fake numbers in the real formats. Sample lot A: county ID `0000-X-00000-0000-00` (matches the mockups), city block-lot `0-X-1`. Then `0000-X-00001-0000-00` / `0-X-2`, and so on. Display names "Sample lot A", "Sample lot B" … No owner names, only owner type.

## Fact distributions (candidates)

| Fact | Distribution |
|---|---|
| zoning district | R1D-M 20%, R2-M 35%, R3-M 25%, RM-M 15%, LNC 5% |
| lot area | 1,800–6,500 sq ft |
| owner type | private 70%, land bank 15%, URA 8%, city 7% |
| assessed value | $4k–$40k; listed price on 40% of lots at 0.8–2.2 × assessed |
| share of lot on 25%+ slope | 0 for 60%, 0.05–0.15 for 25%, 0.25–0.60 for 15% |
| undermined share | > 0 for 20% |
| flood zone share | > 0 for 5% (river edge only) |
| combined sewer | 70% |
| street acceptance | null (unknown, with reason) for 15% |
| tax delinquent | 12% |

## Stage 1 mock scoring (deleted when the engine lands)

Units by right: R1D → 1 (+ ADU), R2 → 2, R3 → 3, RM → 4+. Above the limit needs a variance. Components: approval path (by-right 34, special exception 24, variance 16, rezoning 6, out of 35), site cost (35 minus slope, undermining, sewer and flood penalties), land headroom (out of 30, from max land price vs. listed or assessed). Bands: fast track ≥ 75 with no deal-risk flag; conditions 55–74; high risk < 55; unknown if zoning or street data is missing. Ranges as p10/p50/p90.

## Required special cases

Sample lot A exactly as in `fixtures/mock/ui-draft/sample_lot_a.analysis.json` (rank 1 for "3 townhomes in Hazelwood"); at least 2 unknown lots; 1 lot with a deal-risk slope flag; 1 two-lot assembly; 3 near misses; 1 parcel outside the city with "Zoning not covered for Mt. Lebanon".

## Map features

A few mock transit stops along a line through Hazelwood, 2 parks and 1 school, as GeoJSON points for the `near` filter and the Layers toggle.
