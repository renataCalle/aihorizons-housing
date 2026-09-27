# api/ — Pencil It API

Read the root `CLAUDE.md` first: its boundary rules, contract invariants and commands apply here. This file adds what's specific to the API.

## What it does

FastAPI service (`navigator-api`) that serves the web app. It imports `navigator_engine` and `navigator_contracts` as libraries (never over the network) and adds:
- parcel lookup by county ID, city block-lot or address,
- search: filter and rank precomputed parcel summaries,
- AI search: plain-language text → `SearchFilters` (`docs/05-ai-search.md`),
- GeoJSON for the map (reprojected to EPSG:4326; contracts store EPSG:2272),
- report, evidence and neighborhood summary endpoints.

Endpoints, layout and the site-source interface: `docs/03-architecture-and-api.md`.

## Rules

- **The API never computes judgments.** Scores, flags, severities, program options and next steps come from `navigator_engine`. The API only filters, sorts, formats and serves.
- **AI search only produces filters.** It never decides zoning, scores or rankings (root CLAUDE.md: LLMs extract data and write narrative only).
- **Contracts:** request and response models come from `navigator_contracts`. New API-only models (search filters, parse results, lookup matches) are proposed as **additive** models in `contracts/` (see `docs/proposals/`), never renames or type changes without both owners' approval.
- **Mock vs. real:** a `SiteSource` setting (`mock` or `pipeline`) decides where SiteContext and precomputed summaries come from. The mock must return valid contract objects and mark them illustrative.
- **Secrets:** `ANTHROPIC_API_KEY` only in `.env` (gitignored) and CI secrets. Commit `.env.example`.
- **No personal data:** never return owner names, only owner type.

## Dependencies

Add with uv from the repo root (`uv add --package navigator-api anthropic rapidfuzz`), then `uv lock` so CI's `--locked` passes. Keep geo libraries (pyproj, geopandas) out of the engine; if the API needs reprojection, prefer the pipeline storing a WGS84 geometry, otherwise add pyproj to the API only.

## Done means

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run lint-imports` all pass. The AI search eval (`fixtures/eval/nl_search_eval.jsonl`) runs with `uv run pytest -m eval`.
