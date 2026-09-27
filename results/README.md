# Results bundle: Hazelwood

Pre-computed screening results for **3,625 parcels** in Hazelwood (plus
8 golden test parcels). The API and the demo read these files; they do not
need the 1 GB data store. Generated 2026-09-27 by engine 0.1.0,
rules `rules drafts 2026-09-26`, contracts 0.1.0.

**Regenerate** (needs the local data store; see pipeline/README.md):

```bash
uv run python -m navigator_pipeline.publish
```

Candidates are the 1,018 vacant lots (county land use "VACANT LAND", no
structure) plus the golden parcels. Engine picks: 818 high risk, 199 feasible with conditions, 1 not scored.

## Files

| File | What it holds |
|---|---|
| `summaries.json` | One summary per parcel (all 3,625): the API's `ParcelSummary` shape. Non-candidates have no score. |
| `summaries.csv` | One row per candidate and building type (5,090 rows). Columns below. |
| `site_analysis.jsonl.gz` | One line per candidate: `{"parcel_id", "analysis": SiteAnalysis}`, the engine's pick. |
| `site_context.jsonl.gz` | One line per candidate: `{"parcel_id", "context": SiteContext}`, the facts the engine used. Re-run the engine from these for other buildings or assumptions (about 10 ms each). |
| `parcels.geojson` | Parcel outlines, EPSG:4326, simplified by 0.5 ft, 6 decimals. Properties: `parcel_id`, `block_lot`. |
| `map_features.geojson` | The neighbourhood outline, its parks and transit stops (`kind`, `name`). |
| `manifest.json` | Versions, counts, the as-of date of every data source, and a checksum per file. |

Load and validate everything in Python with `navigator_pipeline.bundle.load()`.

## summaries.csv columns

| Column | Meaning |
|---|---|
| `parcel_id`, `block_lot` | County ID (16 characters) and the city's dashed block-lot |
| `neighborhood`, `zoning_district` | City neighbourhood; the zoning district covering most of the lot |
| `lot_area_sqft`, `owner_type` | Lot area from the parcel map; owner type (private, city, land_bank, ura, other_public). No owner names |
| `assessed_value` | County assessed land value, USD (the default land price; not a market price) |
| `product`, `units` | Building type tested and its unit count (the largest the zoning rules allow, else the smallest tested) |
| `lead` | True for the building type the engine picks for this lot; that row repeats the numbers in site_analysis |
| `score_p10/p50/p90` | Score 0-100 (10th, 50th, 90th percentile of the simulation) |
| `band` | fast_track (75+), feasible_with_conditions (50-74), high_risk (<50), not_scored (zoning not covered) |
| `approval_prob_p10/p50/p90` | Chance the approvals are granted (1 when by right); variances and special exceptions from the Zoning Board model |
| `approval_basis` | Where those odds come from: by_right, model (Zoning Board decisions), measured (City Council votes), placeholder (no decision data yet), joined by `+` |
| `approval_path` | by_right; the approvals needed joined by `+` (e.g. `variance+subdivision`); not_allowed (the zoning rules rule it out); not_covered |
| `months_p10/p50/p90` | Months to permit-ready |
| `cost_premium_p10/p50/p90` | Extra site cost from constraints (slope, undermining, flood...), USD |
| `max_land_p10/p50/p90` | Most a developer could pay for the land at the target margin, USD; negative = costs exceed value |
| `top_flag`, `top_flag_severity` | The most severe constraint and its severity |
| `unknown_flags` | IDs of checks the data could not answer, `;`-separated. Unknown is never clean |
| `lon`, `lat` | Parcel centroid, EPSG:4326 |

Empty cells mean not applicable (no score for a building the rules rule out).

## Limits

- **Screening, not advice.** Costs, prices and approval odds for special exceptions and
  variances are placeholders until local benchmarks and zoning board decisions are available
  (the city's site blocks this client). Every assumption is listed in each analysis.
- **Snapshot.** Built from the stored copy of each source (dates in `manifest.json`); the live
  app refreshes fast-changing records (assessments, liens, permits, sales) per parcel.
- **No evidence file.** Zoning board decisions are not available, so there is no case evidence.
- **Personal data.** Owner type only. Addresses are property addresses from public records.
