# 03 · Architecture and API

This fits the existing monorepo (see the root `CLAUDE.md`): a uv workspace with `contracts/`, `pipeline/`, `engine/`, `research/` and `api/`, plus the npm project in `web/`.

## How the pieces connect

```
web/ (React + MapLibre + deck.gl)
  └── HTTP ──▶ api/ (FastAPI, navigator_api)
                 ├── SiteSource ──── mock:     fixtures → SiteContext
                 │                 └ pipeline: pipeline outputs (DuckDB/Parquet) → SiteContext
                 ├── navigator_engine.analyze(SiteContext) ──▶ SiteAnalysis
                 ├── navigator_engine.analyze_summary(...)  ──▶ per-parcel summaries for search
                 ├── search/: filter + rank summaries, AI search (Anthropic API) + rule-based fallback
                 └── geo/: GeoJSON in EPSG:4326 for the map
```

The engine is pure (root CLAUDE.md), so everything the API needs from data arrives as SiteContext. For the hackathon, search runs over summaries precomputed at API startup (or by a pipeline job) for the parcels in scope, so it's a filter-and-sort, not a live analysis.

## api/ layout

Follow the existing `api/src` layout (likely `api/src/navigator_api/`):

```
navigator_api/
  main.py              FastAPI app, CORS, routers
  settings.py          SITE_SOURCE=mock|pipeline, ANTHROPIC_API_KEY, AI_SEARCH_MODEL
  sources/base.py      SiteSource protocol
  sources/mock.py      MockSiteSource (fixtures)
  sources/pipeline.py  PipelineSiteSource (later)
  search/detect.py     county ID / city block-lot / address / description
  search/parse_ai.py   Anthropic tool-use parser
  search/parse_rules.py  fallback parser
  search/vocabulary.py   thresholds, neighborhood list, aliases
  search/query.py      filter + sort over summaries
  geo.py               EPSG:2272 → 4326 GeoJSON
  routes/              one module per endpoint group
api/tests/
```

## SiteSource interface

```python
class SiteSource(Protocol):
    def site_context(self, parcel_id: str) -> SiteContext: ...
    def candidates(self, area_names: list[str] | None) -> list[str]: ...  # parcel IDs in scope
    def lookup(self, text: str) -> list[LookupMatch]: ...  # IDs and addresses
    def geometry(self, parcel_ids: list[str]) -> dict: ...  # GeoJSON, EPSG:4326
    def neighborhoods(self) -> list[str]: ...
```

Summaries and analyses always come from the engine, so the mock only has to fake the facts (SiteContext) plus geometry. If the engine isn't ready yet, `MockSiteSource` can temporarily return prebuilt SiteAnalysis fixtures (see `docs/06-mock-data.md`).

## Endpoints

Prefix `/api`. Request and response models come from `navigator_contracts` (existing SiteContext and SiteAnalysis, plus the additive search models in `docs/proposals/`).

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | status, site source, engine, ruleset, schema and data versions |
| GET | `/lookup?q=` | lookup matches (county ID, city block-lot, address), max 8 |
| POST | `/search/parse` | `ParseResult` (filters, readings, not_understood, detected) |
| POST | `/search` | `SearchResponse` (total, filters, ranked summaries) |
| GET | `/parcels/{id}` | `ParcelReport`: the report header (`ParcelSummary`) and the engine's `SiteAnalysis` (null when the lot is not a candidate). `?product=&units=` once the engine supports them |
| GET | `/parcels/{id}/evidence/{evidenceId}` | one finding (`flag.<flag id>`) or the approvals option (`option.with_relief`) of the report, same `product_type`/`units` params; zoning board cases when available |
| GET | `/map/parcels` | GeoJSON FeatureCollection in EPSG:4326; properties: `parcel_id, display_name, candidate, band, score, assembly_id`. Ranks come from `/search` and are joined in the client |
| GET | `/map/features` | Transit stops, parks, schools and neighborhood outlines, EPSG:4326 |
| GET | `/neighborhoods` | canonical neighborhood names |
| GET | `/neighborhoods/{name}/summary?product=&units=` | counts per band, top bottlenecks (the engine's `attribute_bottlenecks`; mocked until it exists), near misses, assemblies |

## Parcel IDs

The canonical ID is the county parcel ID; the dashed city block-lot (`16-E-25`) is stored alongside. Lookup and the search box accept county IDs dashed or compact (`0088-B-00044-0000-00`, `0088B00044000000`) and city block-lots (`16-E-25`).

## Geometry

Contracts store EPSG:2272 (PA State Plane South, US survey feet). MapLibre needs EPSG:4326. Agree with the teammate whether the pipeline stores a WGS84 copy (preferred) or the API reprojects with pyproj.

## Frontend state and types

- One filters store is the source of truth; the URL mirrors it (`/search?q=…&f=<base64>`).
- TypeScript types are generated from `/openapi.json` with `openapi-typescript`.

## Config

`.env` (gitignored): `ANTHROPIC_API_KEY`, `SITE_SOURCE=mock`, `AI_SEARCH_MODEL=claude-haiku-4-5-20251001`, `CORS_ORIGINS=http://localhost:5173`. Commit `.env.example`.

## Commands (from the root CLAUDE.md)

```bash
uv sync && uv run uvicorn navigator_api.main:app --reload     # API
uv run pytest && uv run ruff check . && uv run lint-imports   # checks
cd web && npm install && npm run dev                          # web
```
