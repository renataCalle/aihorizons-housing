# Contracts v0.1.0

Latest additive changes: `ProgramOption.resolution` / `resolved_by_step` (how to get the
approvals, and the step that starts it), `ProgramOption.similar_cases` (zoning board
precedents), `SiteAnalysis.code_sections` (every cited code section: title, summary, link,
dates) and `Versions.ruleset_as_of`; before that `ProgramOption.site_cost_premium`,
`SiteAnalysis.rule_checks`, `Source.retrieved` / `retrieved_at`, `Title.recent_permits`. No
version bump; existing clients keep working.

Two Pydantic models are the whole interface between data, engine and UI:

```
backend (pipeline / API)  ──SiteContext──▶  engine.analyze(context, overrides)  ──SiteAnalysis──▶  UI
      facts only                                  judgments                             renders
```

| File | What |
|---|---|
| `src/navigator_contracts/site_context.py` | **Input**: what the backend must supply per site |
| `src/navigator_contracts/site_analysis.py` | **Output**: what the engine returns for the UI |
| `schema/*.schema.json` | JSON Schema for both (`uv run python -m navigator_contracts.export`) |
| `../fixtures/golden/site_context/*.json` | 8 real Pittsburgh parcels, one per spec case |
| `../fixtures/golden/site_analysis/*.json` | The engine's output for each of them |
| `tests/test_golden_fixtures.py` | Every fixture must validate; unknown fields are rejected |

The fixtures are real engine output, not mocks, so they can replace hand-written ones in the
web app today.

## Calling the engine

```python
from navigator_contracts import SiteAnalysis, SiteContext
from navigator_engine import analyze

ctx = SiteContext.model_validate(raw)                                  # from your SiteSource
result = SiteAnalysis.model_validate(analyze(ctx.model_dump(mode="json"), {"land_price": 35000}))
duplex = analyze(ctx.model_dump(mode="json"), program={"product_type": "duplex"})  # ?product=
```

- `overrides` keys are `SiteAnalysis.assumptions[].key` where `editable` is true, plus
  `land_price` (the asking price; default is the assessed land value, or the assessed total
  value for a lot with a building).
- `program` (`?product=&units=`): `{"product_type": ..., "units": int | None}` scores that
  building instead of the engine's pick; it becomes the only option. `units: None` = the
  largest the zoning rules allow. A building the rules rule out comes back `high_risk` with no
  options and the reason in the headline. Unknown types or untested unit counts raise
  `ValueError` (tested counts: `navigator_engine.rules_engine.TEMPLATES`); map it to a 422.
- Pure and deterministic: same input, same output. About 0.01 s per site (spec target: under 1 s).
- Not yet supported: a ruleset other than current, `analyze_summary`, `attribute_bottlenecks`.

## Conventions

- **Ranges**: `{p10, p50, p90}`. Show p10–p90, mark p50. **Intervals** (`cost_usd`, `months`)
  are `[low, high]`; `[0, 0]` means free.
- **Unknown is never clean**: a `null` fact is unknown and its reason is in
  `provenance[layer].note`; an unknown check becomes a flag with `severity: "unknown"`.
- **Shares** are fractions of lot area (0–1); display as percentages.
- **IDs**: `parcel_id` is the 16-character county ID; `block_lot` (e.g. `55-A-137`) alongside.
- **Geometry** in SiteContext is EPSG:2272 (the engine measures in feet). The map's EPSG:4326
  copy is an API/pipeline concern and is not part of SiteContext.
- **Screening language**: never "approved" or "compliant". Engine text already follows this.

## SiteContext: what the backend supplies

| Section | Contents | Reference implementation |
|---|---|---|
| `parcels[]` | ID, block-lot, address, municipality, geometry, lot area, use, structure, assessed values, owner type | `navigator_pipeline.build` (parcels) |
| `zoning[]` | District and overlay codes with share of lot; empty = not covered | `navigator_pipeline.features` `zoning()` |
| `physical` | Slope, landslide, undermined, deep-mined, mine-land shares; FEMA zones; nearby landslides | `features.py` `physical()`, `flood()` |
| `environmental[]` | PA DEP sites within 1,000 ft with distance | `features.py` `environmental()` |
| `infrastructure`, `access` | Combined sewershed, frontage type, water provider; distance to frequent transit | `features.py` |
| `adjacent[]` | Neighbours sharing a lot line and whether they're built | `navigator_pipeline.site_context` |
| `title`, `area` | Liens, condemned, city inventory, recent permits; neighbourhood, market type, QCT, Opportunity Zone | `features.py` `ownership()`, `context()` |
| `market` | Arm's-length sales within 0.5 mi / 3 yrs with building size; HUD rents by bedroom | `site_context.py` |
| `zba_cases_nearby` | Decided Zoning Board cases within 1 mi (up to 25, nearest first): case, decision date, approval types, district, outcome, days to decision, distance, link to the decision | `navigator_pipeline.zba` → `site_context` |
| `provenance` | Source, URL, as-of date and note per layer; `retrieved` = `live` (fetched for this report, with `retrieved_at`) or `snapshot` (from the refreshed store) | `navigator_pipeline.site_context` |

`uv run python -m navigator_pipeline.site_context <parcel> --live` builds any Allegheny County
parcel, and serves as the reference for what a correct SiteContext looks like.

## SiteAnalysis: what the UI renders

Answers to the checklist in `docs/04-contracts.md` (feat/web-api):

| Screen element | Field | Status |
|---|---|---|
| Verdict card | `verdict.{band, score, score_range, land_risk}`, `narrative.summary` | ✓ |
| Where the score comes from | `verdict.components[]` {key, label, points, max_points, note} | ✓ (names match your draft) |
| Headline numbers | `metrics.{months_to_permit, approval_prob, max_land_price, site_cost_premium, land_basis, land_over_max, comps}` | ✓ |
| Flags | `flags[]` worst first: severity, title, cost/months, evidence (source, date, § section, URL), confidence, resolution, `resolved_by_step` | ✓ |
| Cleared checks | `cleared[]` | labels only, no source yet |
| Program options | `options[]` with `label` by_right / with_relief: product, units, unit_sqft, margin, months, relief with § sections | ✓ |
| Approvals: how to get them | `options[].resolution` (who decides each approval and the review procedure) and `options[].resolved_by_step` (→ `next_steps[].order`, the zoning pre-application meeting); both `null` when by right | ✓ |
| What the code requires | `code_sections[]`: every section cited anywhere in the analysis, with `title`, one-line `summary`, `url`, `as_of` (date of the code text) and `effective` (latest amendment). Look a flag's or rule's `§` up here by `section` | ✓ (summaries drafted from the code text, pending a person's review) |
| Code-rule evidence dates | flags resting on a code rule have `evidence[].as_of` (the code text date) and `url`; `versions.ruleset_as_of` is the same date | ✓ |
| Next steps | `next_steps[]`: order, action, who, cost_usd, why | no duration yet |
| Assumptions | `assumptions[]`: key, label, value, min/max, unit, source, editable | ✓ |
| Versions | `versions.{engine, ruleset, schema, data_as_of, ruleset_as_of}` | ✓ (`data_as_of` = oldest input) |
| Evidence drawer: precedents | `options[].similar_cases`: the `case_id`s in `zba_cases_nearby` that count as precedent (rule below); `null` when no zoning board approval is needed or cases are unavailable | ✓ filled from board decisions (2025 on) |
| Rule by rule (why this score) | `rule_checks`: every building type tested, each rule `pass` / `needs_approval` / `rejected` / `not_applicable` with § section and required vs. provided; approval odds per building; site-wide overlay rules; rules not checked yet | ✓ (additive, optional) |

**Names in your draft → names here**: Finding → `Flag` (detail ≈ title + resolution);
NextStep.title → `Step.action`; `cost` → `cost_usd`; headline_numbers → `metrics`;
best_by_right / best_with_approvals → `options[]` by `label`; meta → `versions`; band
`unknown` → `not_scored`. Approval path = "By-right" when `relief` is empty, otherwise the
relief types. Tenure is in `revenue_basis` (for-sale or rental exit).

**Placeholders**: every assumption whose `source` starts with `PLACEHOLDER` is a default,
not a local benchmark. Hard cost drives most results; show the label. Approval odds for
variances and special exceptions come from the Zoning Board approval model
(`entitlement_basis`: "zoning board hearing: model approval_v1 ..."; see
`docs/approval-model.md`); conditional uses and rezonings are measured from City Council votes;
administrator exceptions and subdivisions are still placeholder priors.

**Similar zoning board cases** (`navigator_engine.precedents`): same approval type (variance
or special exception), same base district (R1D for R1D-M), within 0.5 mi, decided in the 5
years before the newest case in the data. The API builds the precedent table (granted count,
median months) from these `case_id`s only.

**Code links**: the code is published on eCode360 (not Municode). Every section links to the
code's home page `https://ecode360.com/PI6865` for now; deep links per chapter can be added in
`engine/src/navigator_engine/config/rules/code_sections.csv` (`url` column) without code
changes.

## Rule by rule: `rule_checks`

Explains *why* a lot gets its options and odds: every building type the engine tested, with
every zoning rule it applied. `null` when zoning isn't covered (outside the city).

- **Rows** (`programs[].checks[].check_id`): `use_allowed` (§ 911.02), `min_lot_size`
  (§ 903.03 / 905.02 / 925.01.C), `fits_envelope` (§ 903.03: setbacks × stories),
  `row_fits_width` and `subdivision` (townhomes only). Each has `section`, `required`,
  `provided`, `unit` and a `note`.
- **Status**: `pass` · `needs_approval` (fixable; `relief_type` names the approval) ·
  `rejected` (not feasible: deviation over 25%, or the use isn't allowed) · `not_applicable`.
- **Odds**: rules are pass/fail; probability comes only from approvals.
  `approval_prob` = product of the odds of each approval a building needs; `1.0` when every rule
  passes; `null` when rejected. Measured odds for conditional uses and rezonings, placeholders
  for the rest (see `entitlement_basis` on options).
- **Columns**: `programs[]` holds every variant tested (~20). Show the ones with
  `representative: true` (one per building type) plus any with `chosen_as` set: those are the
  two headline options in `options[]`, and the tests guarantee they match.
- **Also**: `site_checks[]` (overlays for the whole site: `applies` / `clear` / `unknown`),
  `not_checked[]` (rules not evaluated yet, e.g. parking; show them so users know),
  `scenario` (strict or contextual setbacks), `uncovered_districts`, and `odds_note` (a
  plain-language sentence to show under the table).

Reference rendering: `sandbox/report.py` (`rules_block`).

## Handoff: serving real data from the API

Three sources of real data, for three jobs:

| | Results bundle (`results/`) | Stored scores (`data/scores/`) | Live pipeline |
|---|---|---|---|
| Covers | Hazelwood (3,617 parcels, 1,010 vacant lots scored) + the 8 golden parcels | Every city parcel (142,329), scored once | Any parcel in the county |
| Needs | Nothing: it is in git (8 MB) | The files (~215 MB, not in git); rebuilt from the data store in ~35 min | The local data store (not in git, see below) |
| Freshness | Snapshot; dates in `results/manifest.json` | Snapshot; dates in `data/scores/manifest.json` | Nightly refresh + live per-parcel lookups |
| Use it for | The demo map, lists and search | Any city parcel ID, instantly (SQL or Python) | The latest records for the parcel a user opens |

**1. Results bundle.** `navigator_pipeline.bundle.load()` reads and validates everything
(every line against the contracts; CI checks the bundle on every push):

```python
from navigator_pipeline import bundle
b = bundle.load()                  # results/ at the repo root
b.summaries                        # list of dicts in your ParcelSummary shape (all parcels)
b.analyses[pid], b.contexts[pid]   # SiteAnalysis / SiteContext per candidate
b.parcels, b.map_features          # GeoJSON, EPSG:4326 (parcel_id + block_lot; kind + name)
```

A `BundleSiteSource` is `MockSiteSource` with these inputs:

| Method | From the bundle |
|---|---|
| `summaries` / `summary` | `TypeAdapter(list[ParcelSummary]).validate_python(b.summaries)` |
| `analysis(pid)` | `b.analyses[pid]`; with `?product=` or edited assumptions: `analyze(b.contexts[pid].model_dump(mode="json"), overrides, program)` (~10 ms) |
| `parcels_geojson` | geometry from `b.parcels`, properties from the summaries (as `MockSiteSource` does) |
| `map_features` | `b.map_features` (neighbourhood outline, parks, transit stops) |
| `versions` | `b.manifest["versions"]`, data dates in `b.manifest["data_as_of"]` |
| `evidence` | `None`: zoning board decisions are unavailable |

`results/summaries.csv` has one row per lot and building type (for filters such as "duplexes by
right"); columns are in `results/README.md`. Regenerate the bundle with
`uv run python -m navigator_pipeline.publish` after a refresh or an engine change.

**2. Stored scores (every city parcel).** `uv run python -m navigator_pipeline.score_all`
scores all 142,329 city parcels once (the same `analyze` the API calls, from the stored copy,
no live traffic) and writes four Parquet tables sorted by parcel ID to `data/scores/`. A lookup
reads one small row group: a few milliseconds, no engine run.

```python
from navigator_pipeline import scores
s = scores.load()                          # data/scores/
s.summary("55-A-225")                      # flat row: facts, score, band, ranges, status
s.analysis("0055A00225000000")             # the full SiteAnalysis JSON, as the engine returned it
s.context("0055A00225000000")              # SiteContext, to re-run with overrides or ?product=
s.programs("0055A00225000000")             # one row per building type
s.sql("SELECT neighborhood, count(*) FROM parcels WHERE band = 'fast_track' GROUP BY 1")
```

Or plain SQL from any DuckDB client:

```sql
SELECT analysis FROM 'data/scores/analyses.parquet' WHERE parcel_id = '0055A00225000000';
SELECT parcel_id, score, band FROM 'data/scores/parcels.parquet'
 WHERE neighborhood = 'Hazelwood' AND vacant ORDER BY score DESC LIMIT 20;
```

For the API, a source can serve `analysis(pid)` from `s.analysis(pid)` and fall back to the live
pipeline when a user asks for fresh records. Parcels that could not be scored are kept with
`status = 'error'` and the reason (83 have no county assessment record, 75 too few comparable
sales to price); `not_scored` means
zoning is not covered. Columns are listed in `pipeline/README.md`.

**3. Live pipeline (any parcel).** Needs the data store in `data/` (or `NAVIGATOR_DATA_DIR`).
It is no longer tracked in git. The copy committed earlier is still in history, so the fastest
way to get one is to extract it, then refresh:

```bash
git archive 5552051 data/clean data/features data/raw | tar -x   # ~230 MB, as of 2026-09-26
uv run python -m navigator_pipeline.refresh                       # bring it up to date
```

**Pulling this change deletes the tracked copy from your working tree**; run the `git archive`
line afterwards to get it back as untracked files. Building from scratch instead takes about
30 minutes: `fetch`, `build`, `features` (`pipeline/README.md`).

```python
from navigator_contracts import SiteAnalysis, SiteContext
from navigator_engine import analyze
from navigator_pipeline import site_context

ctx = SiteContext.model_validate(site_context.build([parcel_id], live=True))
analysis = SiteAnalysis.model_validate(analyze(ctx.model_dump(mode="json"), overrides))
```

The first call in a process loads the tables (~2 s); after that a context takes ~0.1 s plus
1–2 s of live lookups (cached for an hour). Tables reload by themselves when the refresh
rewrites them. Reference data for other methods: `data/clean/parcels.parquet` (geometry,
`block_lot`, `address` for lookup), `data/features/parcel_facts.parquet` (one row per city
parcel), `data/clean/{transit_stops,parks,neighborhoods}.parquet`.

**Freshness.** Show `provenance[...].retrieved` (`live` / `snapshot`) and `retrieved_at` in
the report. Install the nightly refresh where the API runs (`pipeline/README.md`).

## Changing the contract

Additive fields are free; renames, removals and type changes bump `SCHEMA_VERSION` and need
both owners to approve the PR. Regenerate fixtures with `uv run python -m sandbox.golden
--export`, the results bundle with `uv run python -m navigator_pipeline.publish`, and schemas with `uv run python -m navigator_contracts.export`; CI checks every
fixture against the models.
