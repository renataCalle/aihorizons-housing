# Contracts v0.1.0

Latest additive changes: `SiteAnalysis.rule_checks` (rule-by-rule explanation);
`Source.retrieved` / `retrieved_at` and `Title.recent_permits` (live data). No version bump;
existing clients keep working.

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
from sandbox.engine_v0.analyze import analyze   # moves to navigator_engine.analyze, same signature

ctx = SiteContext.model_validate(raw)                                  # from your SiteSource
result = SiteAnalysis.model_validate(analyze(ctx.model_dump(mode="json"), {"land_price": 35000}))
```

- `overrides` keys are `SiteAnalysis.assumptions[].key` where `editable` is true, plus
  `land_price` (the asking price; default is the assessed land value).
- Pure and deterministic: same input, same output. About 0.01 s per site (spec target: under 1 s).
- Not yet supported: choosing a product/units (`?product=&units=`), a ruleset other than
  current, `analyze_summary`, `attribute_bottlenecks`.

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
| `zba_cases_nearby` | `null` for now: zoning board decisions are not yet available | — |
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
| Next steps | `next_steps[]`: order, action, who, cost_usd, why | no duration yet |
| Assumptions | `assumptions[]`: key, label, value, min/max, unit, source, editable | ✓ |
| Versions | `versions.{engine, ruleset, schema, data_as_of}` | ✓ (`data_as_of` = oldest input) |
| Evidence drawer: precedents | — | blocked: needs zoning board decisions |
| Rule by rule (why this score) | `rule_checks`: every building type tested, each rule `pass` / `needs_approval` / `rejected` / `not_applicable` with § section and required vs. provided; approval odds per building; site-wide overlay rules; rules not checked yet | ✓ (additive, optional) |

**Names in your draft → names here**: Finding → `Flag` (detail ≈ title + resolution);
NextStep.title → `Step.action`; `cost` → `cost_usd`; headline_numbers → `metrics`;
best_by_right / best_with_approvals → `options[]` by `label`; meta → `versions`; band
`unknown` → `not_scored`. Approval path = "By-right" when `relief` is empty, otherwise the
relief types. Tenure is in `revenue_basis` (for-sale or rental exit).

**Placeholders**: every assumption whose `source` starts with `PLACEHOLDER` is a default,
not a local benchmark. Hard cost drives most results; show the label.

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

## Changing the contract

Additive fields are free; renames, removals and type changes bump `SCHEMA_VERSION` and need
both owners to approve the PR. Regenerate fixtures with `uv run python -m sandbox.golden
--export` and schemas with `uv run python -m navigator_contracts.export`; CI checks every
fixture against the models.
