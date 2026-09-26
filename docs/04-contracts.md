# 04 · Contracts: aligning the UI with `navigator_contracts`

**The source of truth is `contracts/` (`navigator_contracts`): `SiteContext` (facts, built by the pipeline) and `SiteAnalysis` (judgments, built by the engine).** The UI is built to render those. Nothing in this doc overrides them.

## What the UI adds

The web app and API need a few models the scaffold doesn't have yet. They're API-level and purely **additive**, so under the root CLAUDE.md's rules they can be added without a schema-version bump, but both owners should still agree:

| Model | Purpose |
|---|---|
| `SearchFilters` | The single filter state shared by the chips, the filter editor and AI search |
| `ProductFilter`, `NearFilter` | Parts of `SearchFilters` |
| `ParseRequest`, `ParseResult`, `Reading` | AI search input and output |
| `ParcelSummary` | One result row, map feature and inspector card |
| `SearchResponse`, `LookupMatch` | Search and lookup responses |
| `NeighborhoodSummary`, `Blocker` | 3D view side panel |

Their draft definitions are in `docs/proposals/ui-contracts-draft.py.txt` (the search part), with the JSON schema for `SearchFilters` in `docs/proposals/search_filters.schema.json`. Proposal: add them as `navigator_contracts/search.py`.

## What the UI needs from SiteAnalysis

The rest of the draft file (`Verdict`, `Finding`, `ProgramOption`, `NextStep`, `Evidence` …) is **not** a competing contract. It describes what the screens display. Compare it with the real `SiteAnalysis` and turn any gap into an additive field request. The checklist:

| Screen element | Needs from SiteAnalysis |
|---|---|
| Verdict card | band (fast track / conditions / high risk / unknown), score and its p10–p90, a one-sentence narrative (engine- or LLM-written, numbers only from structured fields) |
| "Where the score comes from" | an array of score components: label, points, max, short note |
| Headline numbers | approval path (+ approval probability range if the engine has it), months to permit-ready range, constraint cost premium range, max land price at target margin, listed or assessed price, comps count and window |
| Flags ("What could kill this deal") | array ordered worst first: id, severity (deal risk / caution / unknown), title, detail, cost and schedule impact ranges, sources with dates, confidence, which next step resolves it, evidence id |
| Cleared checks | array of checks that came back clean, with source |
| Program options | best by-right and best with approvals: product, units, size, margin range, months range, approval path, relief needed with code sections, precedent counts, evidence id |
| Next steps | array ordered cheapest deal-killer first: title, why, who, cost range, duration |
| Assumptions | array: key, label, value or range, source label, editable |
| Versions | engine, ruleset, schema and data as-of (already required by the root CLAUDE.md) |
| Evidence drawer | code section with date and plain summary; precedent counts, median months, case list (id, neighborhood, request, outcome, months, source link); AI-extracted flag; confidence note; how to resolve |

## Differences to reconcile

- **Ranges:** the repo uses p10/p50/p90. The draft uses low/high. **The repo wins:** the UI shows p10–p90 and can mark p50.
- **Score components:** the root CLAUDE.md builds the score from approval probability, months to permit-ready and constraint cost premium. The mockups show approval path, site cost and land headroom. Render whatever components the engine returns; the mockup labels are only examples.
- **Overlay facts** are shares of lot area (0–1). The UI formats them as percentages ("8% of the lot").
- **Parcel IDs:** county ID canonical, city block-lot alongside. Search and lookup accept both.
- **Geometry:** EPSG:2272 in contracts; the map needs EPSG:4326 (see `docs/03`).

## TypeScript types

Generated from FastAPI's `/openapi.json` with `openapi-typescript`, never hand-written.
