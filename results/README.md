# Results bundle (real data)

What the API serves with `SITE_SOURCE=pipeline`: real Pittsburgh parcels, their facts from the
pipeline's store, and the engine's analysis of each candidate lot. About 4 MB, compressed.

| File | What |
|---|---|
| `summaries.json.gz` | One `ParcelSummary` per parcel in scope (search, list, map colors, report header) |
| `parcels.geojson.gz` | Parcel shapes, EPSG:4326, simplified to 0.5 ft, 6 decimals |
| `map_features.geojson.gz` | Frequent transit stops (64+ weekday trips), parks near the scope, all 90 neighborhood outlines |
| `site_analysis.jsonl.gz` | One line per candidate: `{"parcel_id", "analysis"}` with the full `SiteAnalysis` |
| `manifest.json` | Scope, counts, engine/ruleset/schema versions, each source's as-of date |

## Scope

Every parcel in Hazelwood, Greenfield and Glen Hazel is on the map. The candidates, scored by the
engine, are their vacant lots of 1,500–20,000 sq ft, plus the 8 golden parcels. Parcels that
aren't candidates carry facts only (address, zoning, lot size, use, owner type).

## How it's built

```bash
NAVIGATOR_DATA_DIR=/path/to/data uv run python api/scripts/build_results_bundle.py
```

The script reads the pipeline's runtime store (`data/`, see `pipeline/README.md`), builds each
candidate's `SiteContext` with `live=False` (the stored copy, so the bundle is reproducible),
runs the engine, and writes the files above. About two minutes.

## Rules

- **Commit the results, not the store.** Rebuild after the store or the engine changes, and
  commit rarely: every commit of these files stays in the history for good.
- **No personal data.** Owner type only, never owner names. The store's cleaned tables already
  drop owner names and mailing addresses.
- **Validated in CI.** `api/tests/test_results_bundle.py` loads every file with the contracts and
  checks that every candidate has an analysis and every parcel a shape.
- **Screening, not approval.** Every analysis is a screening estimate from the engine version
  in `manifest.json`, not a zoning determination.

## Data sources

Allegheny County parcels and assessments, City of Pittsburgh zoning, overlays and hazard layers,
FEMA flood zones, PA DEP mine and environmental records, Port Authority transit stops, HUD rents
and market data from WPRDC. `manifest.json` lists every source with its as-of date; the full
catalog with URLs is in `navigator_pipeline.catalog`.
