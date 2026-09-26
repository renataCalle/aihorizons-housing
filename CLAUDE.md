# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Development Feasibility & Pro Forma Navigator takes a Pittsburgh parcel ID, address, or
map click and returns a screening verdict: a 0–100 Development Ease Score built from approval
probability, months to permit-ready, and constraint cost premium, plus flags, program options,
a pro forma, and next steps. The full product spec is "Development Feasibility & Pro Forma
Navigator — Specification.md" (kept outside the repo); consult it before designing any module.

The repo is currently a scaffold: package folders, tooling, and CI, with no domain code yet.

## Commands

Python is a uv workspace (one `uv.lock` for all packages); the web app is a separate npm project.

```bash
uv sync                                   # install workspace (add --extra notebooks for JupyterLab)
uv run pytest                             # all Python tests
uv run pytest engine/tests/test_smoke.py::test_package_imports   # single test
uv run ruff check . && uv run ruff format --check .              # lint + format check
uv run lint-imports                       # architectural boundary rules (see below)

cd web && npm install
npm run dev | npm run build | npm run lint   # Vite dev server, tsc + build, oxlint
```

CI (`.github/workflows/ci.yml`) runs `uv sync --locked`, ruff, lint-imports, and pytest, plus
`npm ci`, lint, and build in `web/`. After changing any `pyproject.toml`, run `uv lock` so
`--locked` passes.

## Architecture

**Facts vs. judgments.** The engineer delivers facts; the research scientist delivers judgments.
A fact is measurable from data without assumptions (lot area, share of lot on ≥25% slope,
distance to a DEP site, nearby zoning board cases). A judgment needs a model, threshold, or
assumption (cost premium, severity, approval probability, score, recommendations). Two
versioned Pydantic contracts in `contracts/` are the only interface between the two:

- `SiteContext` (facts): built by `pipeline/`, the ingestion and feature builder.
- `SiteAnalysis` (judgments): built by `engine/` via `analyze`, `analyze_summary`,
  `attribute_bottlenecks`, `list_rulesets`.

`api/` (FastAPI) imports the engine as a library, not a service. `web/` (React + MapLibre)
renders SiteAnalysis generically: flags, assumptions, and next steps are arrays, so new flag
types or editable assumptions need no frontend change. TypeScript types are meant to be
generated from the Pydantic contracts.

**Boundary rules, enforced by import-linter in the root `pyproject.toml`:**
- `navigator_engine` is pure: no network or database access, and it may not import pipeline,
  api, research, duckdb, geopandas, httpx, requests, or fastapi. Everything the engine needs
  arrives in SiteContext or lives in versioned config inside `navigator_engine/config/`
  (rules tables, cost tables, fitted parameters).
- `navigator_contracts` imports nothing from the workspace.
- `navigator_research` (notebooks and prototypes) is never imported by engine, pipeline, or api.
  A useful research feature becomes a SiteContext field request to the engineer.

Keep heavy geo and database dependencies out of `engine/pyproject.toml`; they belong in `pipeline`
and `research`.

**Contract invariants the code must honor:**
- Overlay facts are shares of lot area (0–1), never booleans. A missing fact is null with a
  reason in `provenance`, never zero; a missing fact yields an `unknown` flag, never a clean one.
- Geometry is PA State Plane South, US survey feet (EPSG:2272). Parcels use one canonical
  county ID, with the dashed city block-lot (e.g. `16-E-25`) stored alongside.
- Zoning rulesets are versioned by effective date (the city code is actively being amended);
  scenario rulesets encode proposed amendments.
- Every estimate is a p10/p50/p90 range. Every SiteAnalysis stamps engine, ruleset, schema,
  and data as-of versions.
- Screening language only: never "approved" or "compliant", only "by-right under the code as
  of <date>".
- Compliance logic is deterministic code. LLMs only extract data (zoning board decisions,
  draft rules rows for human review) and write narrative; the narrative may contain no number
  absent from the structured fields.
- `analyze`, Monte Carlo included, should finish in under 1 second.

**Contract changes:** additive fields are free. Renames, removals, and type changes bump the
schema version and need approval from both owners.

`fixtures/golden/` holds paired `site_context/` and `site_analysis/` JSON for the eight golden
Pittsburgh parcels. They become snapshot tests, so an engine change that moves a golden score
is visible to both owners.

Raw data never goes in git; `data/`, `*.duckdb`, `*.parquet`, and shapefiles are gitignored.
