# aihorizons-housing

Development Feasibility & Pro Forma Navigator: a parcel ID or map click in, a site feasibility
verdict out. Pittsburgh zoning in v1; physical, environmental, infrastructure, and market
layers countywide.

## Layout

| Folder | What lives there | Owner |
| --- | --- | --- |
| `contracts/` | `SiteContext` (facts) and `SiteAnalysis` (judgments) Pydantic models | Both |
| `engine/` | Pure-Python feasibility engine plus its versioned config | Research scientist |
| `research/` | Notebooks and prototypes, read-only database access | Research scientist |
| `pipeline/` | Data ingestion and the SiteContext feature builder | Engineer |
| `api/` | FastAPI service that imports the engine as a library | Engineer |
| `web/` | React + MapLibre app | Engineer |
| `fixtures/golden/` | Golden-parcel `site_context/` and `site_analysis/` fixtures | Both |
| `results/` | Committed results bundle (Hazelwood): what the demo serves without the data store | Research scientist |
| `sandbox/` | Research tools: rules extraction, golden-parcel picks, parcel CLI and HTML report | Research scientist |

Python packages are members of one [uv](https://docs.astral.sh/uv/) workspace with a single
lockfile. The web app is a separate npm project.

## Boundary rules (enforced in CI by import-linter)

- `engine` makes no network calls and no database reads; it may not import `pipeline`, `api`,
  `research`, or I/O libraries.
- `contracts` depends on nothing else in the workspace.
- `research` is never a dependency of `engine`, `pipeline`, or `api`.

## Run the app locally

The app (Pencil It) is two processes: the API on port 8000 and the web app on port 5173.

**You need:** Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 22 with npm.

**1. Install** (once, from the repo root):

```bash
uv sync
cd web && npm install && cd ..
```

**2. Optional: AI search.** Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.
Search then reads plain-language text with Claude (Haiku 4.5, `AI_SEARCH_MODEL`). Without a
key, or when a call fails (for example no API credit), search still works with the built-in
rule-based parser and shows a "Basic search" tag. `/api/health` reports `ai_search`.

```bash
cp .env.example .env
```

**3. Start the API** (terminal 1, repo root):

```bash
uv run uvicorn navigator_api.main:app --reload
```

It serves the committed Hazelwood results in `results/` (`SITE_SOURCE=pipeline`, the
default). For the illustrative mock lots instead, start it with `SITE_SOURCE=mock`. Check it
at http://localhost:8000/api/health.

**4. Start the web app** (terminal 2):

```bash
cd web && npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` to the API on port 8000.

**Things to try:** search "2 townhomes in Hazelwood"; type a parcel ID such as `52-H-93` and
open its report; in a report, "Evidence →" on a finding or on the "Best with approvals" card;
the "3D" button and the map style switch (palette button, or Layers).

**If something looks off:** restart the API after `results/` changes (it loads the data at
startup). If port 8000 is taken, run the API with `--port 8010` and the web app with
`API_URL=http://127.0.0.1:8010 npm run dev`.

## Checks (what CI runs)

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run lint-imports
cd web && npm run lint && npm test && npm run build
```

## Working agreements

- Contract changes go through a pull request both owners approve. Additive fields are
  same-day changes; renames, removals, and type changes bump the schema version.
- Raw data never goes in git (`data/` is ignored).
