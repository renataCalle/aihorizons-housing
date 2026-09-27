# 07 · Build plan

Build in this order, on your own branch (`feat/web-api`), merging with normal merge commits. Every milestone must leave CI green: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run lint-imports`, and in `web/`: `npm run lint`, `npm run build`. Before each milestone, Claude Code shows a short plan; after it, compare the screen with its PNG in `docs/design/screens/`.

## M0 · Foundation

- Read the root `CLAUDE.md`, `web/CLAUDE.md`, `api/CLAUDE.md` and `docs/`. Inspect `contracts/` and report how the real SiteContext/SiteAnalysis compare with `docs/proposals/ui-contracts-draft.py.txt`.
- API: FastAPI app in `api/src/`, `/api/health` with versions, `SiteSource` protocol, `MockSiteSource` serving `fixtures/mock/ui-draft/`.
- Propose the additive search models (`navigator_contracts/search.py`) as a separate small PR for the teammate to approve.
- Web: replace the Vite starter; add `tokens.css`, fonts, React Router, the filters store, the API client and generated types (`openapi-typescript`).
- **Done when:** `/api/health` and the Sample lot A analysis respond, CI is green, and the web app loads with the right fonts and colors.

## M1 · Blueprint map

- MapLibre 6 with OpenFreeMap Positron recolored by `applyBlueprintTheme`.
- Mock generator (`docs/06-mock-data.md`); `/api/map/parcels` in EPSG:4326; band fills, hatch for unknown, outlines, selection crosshair.
- Glass shell: top bar, map controls, coordinate and scale readout.
- **Done when:** the map matches `MapBase` and clicking a parcel selects it.

## M2 · Landing and search box

- Landing screen; search box detection (county ID, city block-lot, address, description) with Vitest tests; `/api/lookup` dropdown; example chips.
- **Done when:** typing `0000-X-00000` shows Sample lot A with its score, and Enter opens `/parcel/0000-X-00000-0000-00`.

## M3 · Search and AI search

- `/api/search` (filter, sort, ranks) and `/api/search/parse` (detection, forced tool use, fallback parser, normalization, merge).
- AI preview with editable chips and readings; results screen with filter chips, "Edit filters", ranked list, legend, Layers, list–map sync, inspector card.
- Eval test over `fixtures/eval/nl_search_eval.jsonl` (`uv run pytest -m eval`).
- **Done when:** the sample prompt returns Sample lot A first, the chips match `fixtures/mock/ui-draft/sample.parse_result.json`, and the eval prints an accuracy table.

## M4 · Report and evidence

- Report panel rendered generically from SiteAnalysis (flags, score components, assumptions, next steps are arrays); p10–p90 ranges; the map shift and "Back to N sites".
- Evidence drawer; print stylesheet for "Export memo"; loading, empty, error, outside-city and unknown states.
- **Done when:** the Sample lot A report matches the PNG section by section and prints as a clean two-page memo.

## M5 · 3D view

- **Built:** "3D / 2D" toggle kept in the URL (`view=3d`); tilted camera; the basemap's buildings raised to their heights with MapLibre `fill-extrusion` (no deck.gl), solid and above the lots; selected lot raised 3 m; Blueprint and Standard map themes; toggling back keeps the selection. Replaces the original deck.gl score blocks (see `docs/01-product-spec.md`, 3D view).
- **Built: "at a glance" panel** on the left in 3D (`POST /api/search/summary`, `web/src/results/GlancePanel.tsx`), for the current search, with the ranked list one click away:
  - lots per band, as the search ranks them;
  - "What holds sites back": for each score driver, how many lots it costs points and how many points on average, added up from each lot's `score_breakdown` (the engine's own counterfactuals; the API only counts and averages). Stands in for the planned `attribute_bottlenecks`: confirm with the engine owner;
  - near misses and assemblies.
- **Dropped for lack of data:** the glow under fast-track lots (Hazelwood has none in the current results) and a score tooltip (the inspector card already shows score and band).

## M6 · Polish and submission

- Accessibility pass; shareable URLs; demo script (landing → AI search → results → report → evidence → 3D).
- README: libraries, frameworks, APIs, public datasets, AI tools used, data sources and assumptions, team (all required by the hackathon packet).
- README limitations section must include:
  - Zoning board cases are listed by case number only, without a link to the decision: the decisions are public city documents but name applicants, so links are held back until that's settled (`api/src/navigator_api/evidence.py`, `_case`).
- Secrets scan of the full history before the repo goes public.
- **Done when:** the whole demo runs offline with the fallback parser.

## Switching to real data

When the engine lands: stage 2 of `docs/06-mock-data.md` (analyses from `navigator_engine`). When the pipeline lands: `SITE_SOURCE=pipeline`, golden parcels as the demo set. Revisit the filters and vocabulary (`docs/05-ai-search.md`, last section).

---

## Prompts to paste into Claude Code

**First session:**

```
Read the root CLAUDE.md, web/CLAUDE.md, api/CLAUDE.md, everything in docs/, and the
PNGs in docs/design/screens/. Then inspect contracts/, engine/ and the existing
scaffolding in web/ and api/. Tell me:
1. how the real SiteContext/SiteAnalysis compare with docs/proposals/ui-contracts-draft.py.txt,
   and which additive fields or models the UI needs,
2. anything in the docs that conflicts with the repo's tooling or rules,
3. your plan for milestone M0 in docs/07-build-plan.md.
Don't modify contracts/, engine/, pipeline/ or research/. Don't write code until I approve.
```

**Each milestone after that:**

```
Let's do milestone M<N> from docs/07-build-plan.md. Show me a short plan first.
Keep CI green. When you're done, compare the result with docs/design/screens/<screen>.png
and list any differences you couldn't fix.
```
