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

## Getting started

```bash
uv sync                      # Python workspace (add --extra notebooks for JupyterLab)
uv run pytest                # tests
uv run ruff check .          # lint
uv run lint-imports          # boundary rules

cd web && npm install && npm run dev
```

## Working agreements

- Contract changes go through a pull request both owners approve. Additive fields are
  same-day changes; renames, removals, and type changes bump the schema version.
- Raw data never goes in git (`data/` is ignored).
