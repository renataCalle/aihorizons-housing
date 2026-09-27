# 08 · What we built: functional spec of the app as it stands

State of `main` at `f0d22ac` (27 Sep 2026), plus the planner work on `feat/web-api` (the Area view and "starter homes", marked as such). This lists every feature that exists in the code,
what it does, and where it lives. Status marks: **Built**, **Built, switched off**, **Not built**
(specified in `docs/01`–`07` but not in the app). The product spec (`docs/01-product-spec.md`)
says what was planned; this file says what is there.

The app is called **Pencil It**. It serves two of the Challenge 01 personas:

- **Small/mid-size developer** (3–20 homes): *should I spend money on this site, and if so, on
  what?*
- **Municipal planner** (City Planning, the County, agencies): *which sites are ready for
  housing, and which rules or infrastructure gaps hold the rest back?*

---

## 0. Personas and the brief's use cases

| Challenge 01 use case | Persona | What the app does today | Status |
|---|---|---|---|
| Developer enters a parcel ID and gets a Development Ease Score and bottlenecks | Developer | Search box → site report: score with range, three score parts, findings worst first with sources, what can be built, next steps, evidence | Built |
| Planner compares multiple parcels to find sites suited to starter homes | Planner | Search for a building type ("starter homes", single house, duplex, townhomes) in chosen neighbourhoods; ranked list and map coloured by band; sort by score, land price, time to permit, land headroom; inspector card per lot | Partly built: no side-by-side compare of chosen lots |
| City finds low-scoring sites and asks whether zoning reform or infrastructure upgrades are needed | Planner | Each report shows the points every problem costs and a rule-by-rule table; near misses list lots one filter away; the **Area view** adds up "what holds sites back" across the searched lots, including lots that can't pay for their land | Built on `feat/web-api`, except a "what if this rule changed" rerun |
| Agencies prioritise investment by score clusters across neighbourhoods | Planner | Map coloured by band; lots per band for the searched area in the Area view | Partly built: one area at a time, no neighbourhood-by-neighbourhood comparison |

Housing nonprofits/CDCs use the developer flow plus the "Public land" filter (land bank, URA,
city). Policy analysts use the planner flow.

**Planner work:**

1. **Done (`feat/web-api`): Area view.** A "Lots / Area view" switch at the top of the left
   panel, in 2D and 3D, kept in the URL (`panel=area`). It shows lots per band, what holds
   sites back and near misses (with "See them", which opens the list with near misses shown).
   "What holds sites back" now also counts **"Sale value doesn't cover costs and land"**: the
   points each lot's land-headroom score falls short of its 30 (in Hazelwood, 718 of 1,010
   lots lose all 30).
2. **Done (`feat/web-api`): "starter homes"** searches for single-family homes (the engine's
   closest building type). Two eval prompts added.
3. Not started: Compare. Pick 2–5 lots from the list and see score, band, path, top risk and
   max land price side by side.
4. Not started: Neighbourhood clusters. Counts per band and the top barrier per
   neighbourhood, from the same summary endpoint called per area.

---

## 1. The data being served

| | |
|---|---|
| Area | Hazelwood (plus Greenfield and Glen Hazel edges), City of Pittsburgh |
| Parcels on the map | 3,625 |
| Development candidates (scored) | 1,018 |
| Bands | 199 feasible with conditions, 818 high risk, 0 fast track, 1 not scored |
| Golden test lots | 8 real parcels, each testing one situation (§8) |
| Public data sources | 46 (assessments, zoning, slopes, mines, floods, DEP records, sales, liens, transit, Council votes, Zoning Board decisions …) |
| Zoning rules encoded | 335 rows from the city code, each with its section and effective date |
| Zoning Board decisions modelled | 202 (Feb 2025 – Aug 2026, 28 denied) |

Everything is precomputed into the committed results bundle (`results/`, written by
`navigator_pipeline.publish`) so the demo needs no database and no network. The API can also
serve illustrative mock lots (`SITE_SOURCE=mock`); those screens carry an "Illustrative data"
badge.

**Why Hazelwood has no fast-track lots:** at the placeholder construction cost ($250/sq ft) most
projects can't pay for their land. That is a real finding, not a bug (technical report §11).

---

## 2. The engine (judgments) — `engine/`

Pure Python, no network or database. `analyze(context, overrides, program)` returns a
`SiteAnalysis` in about 0.01 s.

| Feature | What it does | Status |
|---|---|---|
| Zoning check | Tests five building types (single house, duplex, triplex, 2–8 townhomes, 4–12 unit walk-up) against the district's dimensional rules, allowed uses and standards. Records every rule, pass or fail, with the gap and the approval that would fix it. | Built |
| Buildable envelope | Floor area from lot width/depth minus setbacks, times stories. Applies contextual (match-the-neighbours) side setbacks and the narrow-lot rule. | Built |
| Approval ladder | By right → administrator exception → special exception → variance → conditional use → rezoning. Misses of more than 25% on a dimension are treated as not feasible; use changes are not offered. | Built |
| Overlay rules | Undermined (site investigation for anything bigger than a house), flood zone (no basement, elevation), floodway (near deal-breaker). | Built |
| Site flags | Steep slope, landslide-prone, undermined, flood, nearby DEP records, no street frontage, combined sewer, existing building to demolish, condemned, tax liens, split zoning, contextual setbacks, plus an **unknown** flag for any missing fact. Severity scales with the share of the lot affected. | Built |
| Approval odds | Zoning Board (variances, special exceptions): Bayesian logistic regression on 202 board decisions (`config/models/approval_v1.json`). Council (conditional use, rezoning): measured from Council votes 2000–2026. Administrator exception, subdivision: expert ranges. | Built |
| Months to permit-ready | Permit review plus the longer of approvals or site studies. | Built |
| Pro forma | Sale value from nearby sales (new-build comps, or older homes plus a premium); rental value for walk-ups; costs, fees, contingency, site costs, carry. Output: **max land price** at a 15% target margin. | Built |
| Monte Carlo | 2,000 draws of costs, prices, delays and approval odds; every number is a p10/p50/p90 range. | Built |
| Score (0–100) | Approval path (35) + site cost (35) + land headroom (30). Bands: ≥75 fast track, 50–74 feasible with conditions, <50 high risk. | Built |
| Score breakdown | Points each flag costs (the score recomputed without it). | Built |
| Verdict pick | Which project the verdict describes (by-right if profitable; else best profitable; else least risky). | Built |
| Next steps | One check per flag, with who, cost and time, ordered free first, then most likely to kill the deal for the least money. | Built |
| Narrative | One plain sentence; contains no number absent from the structured fields. | Built |
| Versions | Engine, ruleset, schema and data as-of stamped on every analysis. | Built |
| `analyze_summary`, `attribute_bottlenecks`, `list_rulesets` | Planned engine functions. The API computes summaries and "what holds sites back" from stored analyses instead. | Not built |

Placeholders that still drive results: construction cost, site-cost ranges, score weights,
kill probabilities for next steps. Listed in technical report Appendix B.

---

## 3. The data pipeline (facts) — `pipeline/`

| Feature | Status |
|---|---|
| `fetch`: downloads 46 sources with provenance manifests (`catalog.py`) | Built |
| `build`: clean GeoParquet in EPSG:2272 | Built |
| `features` / `site_context.build`: per-parcel facts as shares of lot area, distances, nearby records; missing = null with a reason | Built |
| `refresh`: re-pulls changed sources on each source's cadence | Built |
| `live`: fetches fast-changing per-parcel records (assessment, liens, condemned, city ownership, permits, new sales) at report time, falls back to the stored copy | Built |
| `score_all` / `scores`: every city parcel scored once into Parquet, queryable by ID or SQL | Built |
| `zba_download` + `zba`: Zoning Board agendas and decisions (2025 on) parsed to cases linked to parcels, no names kept | Built |
| `publish` / `bundle`: the committed Hazelwood results bundle and its loader | Built |

---

## 4. The API — `api/` (FastAPI, imports the engine as a library)

| Endpoint | Returns | Status |
|---|---|---|
| `GET /api/health` | Status, site source, versions, whether data is illustrative, whether AI search is on (`ai_search`) | Built |
| `GET /api/examples` | A parcel ID, an address and an AI prompt taken from the data served, for the landing chips | Built |
| `GET /api/lookup?q=` | Up to 8 matches on county ID (dashed, compact, partial), city block-lot or address, with score and band | Built |
| `POST /api/search/parse` | Plain language → `SearchFilters`, plus readings and anything not understood. AI parser (`search/parse_ai.py`): Claude Haiku 4.5 with one forced tool call whose schema is `SearchFilters` (neighbourhoods limited to the city's 90 names); it returns only the fields asked about, which are validated, alias-expanded and merged with the current filters; answers cached per process. Falls back to the rule-based parser (keywords, regex, fuzzy matching for typos) with no key or on any API error, and says which one answered (`parser`) | Built |
| `POST /api/search` | Filtered, ranked lots; removable filter chips; near misses (one filter away); an empty-state suggestion ("remove X → N sites"); filters it couldn't apply | Built |
| `POST /api/search/summary` | Lots per band, what holds sites back, near misses, assemblies (for the Area view) | Built; land headroom added on `feat/web-api` |
| `GET /api/neighborhoods` | Names with candidate counts | Built |
| `GET /api/parcels/{id}?product=&units=` | Report header plus the engine's `SiteAnalysis`; re-scores for a chosen building type; 422 with the tested range for sizes the engine doesn't test | Built |
| `GET /api/parcels/{id}/evidence/{evidenceId}` | Evidence for one finding (`flag.<id>`) or the approvals option (`option.with_relief`): sources, code sections, odds, similar Zoning Board cases | Built |
| `GET /api/map/parcels`, `GET /api/map/features` | Parcels (EPSG:4326) with band and score; transit stops, parks, schools, neighbourhood outlines | Built |
| `GET /neighborhoods/{name}/summary` | Replaced by `POST /search/summary` | Not built |

**Search rules:** the parser only fills in filters, it never searches, scores or ranks. Parcel
IDs and addresses go to the lookup, never to the parser. Vocabulary (flat, near transit, no hearing,
public land, cheap, fast …) maps to fixed thresholds; neighbourhood aliases ("Lawrenceville",
"the Hill") expand to canonical names. An eval of 41 prompts (`fixtures/eval/`,
`uv run pytest -m eval`) scores the parser field by field.

---

## 5. The web app — `web/` (React + MapLibre)

### 5.1 Landing (`/`)

| Feature | Status |
|---|---|
| Faded full-screen city map; click any lot to open its report | Built |
| Headline "What can you build here?" and one search box | Built |
| Three example chips (ID, Address, ✦ AI) filled from the served data; clicking fills the box and opens suggestions | Built |
| "Open the map" button; "Illustrative data" badge on mock data | Built |
| "Saved sites" | Not built |

### 5.2 Search box (omnibox, landing and top bar)

| Feature | Status |
|---|---|
| Detects parcel ID / block-lot / address / description as you type, with a "Detected: …" or "AI search" tag | Built |
| Dropdown of matching lots with score and band ("Not a candidate" when unscored); Enter opens the report | Built |
| "Search with AI for …" row for descriptions; Enter runs the search | Built |
| Keyboard: ↑↓, Enter, Esc | Built |
| "How we read it" preview in the dropdown (readings, not understood, "Show N sites") | Not built: the reading shows as filter chips on the results screen instead |
| "Basic search" tag next to the filter chips when the rule-based parser answered (no key, no credit, or an API error) | Built |

### 5.3 Results (`/search?q=…`)

| Feature | Status |
|---|---|
| Top bar: brand, search box with the current query | Built |
| Left panel: "N lots · best first", sort menu (score, land price, time to permit, land headroom) | Built |
| Filter chips, each removable; "Not applied yet (no data)" note for filters without data | Built |
| Edit filters: building type and units, approval path, areas (only areas with sites / all 90), max land price, lot size, flat lots, near transit, vacant only, public land, exclude (undermined, flood, landslide, steep slope, combined sewer), show unknowns, lots that work together, near misses | Built |
| Ranked list with loading skeleton, error + retry, empty state with one-click "Remove X (N sites)" | Built |
| Near misses section: "Fails: <filter>" | Built |
| Legend | Built |
| Layers: map style (Blueprint / Standard), transit stops | Built |
| Layers: steep slope, undermined, flood overlays | Not built (greyed out; need the pipeline's geometry) |
| Map: lots coloured by band for the searched building type, hatched when unknown, outline-only for non-candidates, tint for assemblies; searched neighbourhoods get a dashed boundary with the rest dimmed; rank tags on top results | Built |
| List ↔ map sync (hover a row highlights the lot; click a lot selects its row) | Built |
| Inspector card: "Selected · 01 / N", score and band, path, top risk, max land price, "Open full report" | Built |
| Coordinate and scale readout; zoom; 3D | Built |
| Filters in the URL, so a search is shareable | Built |

### 5.4 Report (`/parcel/:id`)

A panel over the map; "Back to N lots" pill; Esc closes; focus moves into the panel.

| Section | What it shows | Status |
|---|---|---|
| Header | "Site report · 01 / N", Export memo, close | Built |
| Title | Address, neighbourhood, county ID, lot size, zoning, current use | Built |
| Building note | "Scored for 2 townhomes, as searched. Better fit on this lot: … · See it" — switches to the engine's best pick and back | Built |
| Verdict card | Band pill (or "High risk at the assessed value"), score /100 with its likely range, one-sentence headline, "Where the score comes from" bars (approval path, site cost, land headroom) | Built |
| Key numbers | Approval path and months to permit-ready; site cost premium and its drivers; max land price at 15% margin vs assessed or asking price, and the comps used | Built |
| What could kill this deal | Findings worst first: severity, title, how to resolve, source and date, code section, confidence, added cost and months, "See source", "Evidence →"; a "Cleared" line | Built |
| What you can build | Best by-right and best with approvals: units and size, margin, months to permit-ready, approvals, code basis, "Leading option" badge, "Evidence →" on the approvals card | Built |
| Rule by rule | Zoning rules × building types: allowed, needs approval (and by how much), not feasible; approval odds and result rows; site-wide rules; rules not checked yet | Built |
| What to check next | Ordered steps with who and cost; "N free checks first" | Built |
| Parcel and assumptions | Parcel facts; every pro forma assumption with its source or "Placeholder, not a local benchmark" | Built |
| About this report | Versions and data freshness (live lookups vs stored copy) | Built |
| Export memo | Browser print to a PDF memo with a sources appendix | Built |
| Outside the city | "Zoning not covered for <municipality>" with parcel facts | Built |
| Not a candidate | "Not a development candidate" with parcel facts | Built |
| Save | Not built |
| Editable assumptions (change cost, price, margin and re-run) | Not built in the UI (the engine accepts overrides) |

### 5.5 Evidence drawer (`/parcel/:id/evidence/:evidenceId`)

| For | Shows | Status |
|---|---|---|
| A finding | Impact (added cost, added time), sources with dates and links, "What the code says" (section, title, plain summary, dates, link to the code), how to resolve and the next step that does it | Built |
| The approvals option | Each failing rule and the approval it needs, code sections, approval odds, approval months and months to permit-ready, the odds basis ("model of 202 board decisions …"), similar Zoning Board cases nearby (granted count, median months, table of cases with outcome), how to resolve | Built |
| Links to board decisions | Cases listed by number only: decisions name applicants, so links are held back | Deliberately not built |

### 5.6 3D view

| Feature | Status |
|---|---|
| "3D / 2D" button, kept in the URL across results, report and evidence | Built |
| Tilted camera; basemap buildings raised to their mapped heights; lots stay flat and coloured by band; the selected lot raised 3 m | Built |
| Works in both map styles (Blueprint, Standard) | Built |
| Area view (lots per band, "What holds sites back", near misses) | Built, in 2D and 3D (see §0) |
| Glow under fast-track lots; score blocks | Dropped (no fast-track lots in Hazelwood) |

### 5.7 Across the app

| Feature | Status |
|---|---|
| Deep links for every screen (search, report, evidence, 3D) | Built |
| Screening language only ("by-right under the code as of …", never "approved") | Built |
| Money and time as ranges | Built |
| Keyboard access and focus handling in panels and drawer | Built |
| Accounts, teams, saved searches, mobile layout | Not built (out of scope for v1) |

---

## 6. Quality checks

- CI: ruff, import-linter (engine purity), pytest, web lint, tests and build.
- Last end-to-end run (`f0d22ac`): 256 Python tests, 110 web tests, 71 live API checks.
- Golden fixtures are snapshot tests: an engine change that moves a golden score shows up in
  review.
- Search eval: 43 prompts (`uv run pytest -m eval -s`); it uses the AI parser when `ANTHROPIC_API_KEY` works, else the rule-based one, and prints which. Rule-based: 86/86 fields. AI parser (Haiku 4.5): 85–86/86 over two runs (99–100%), about 1–1.5 s per search. The AI parser also reads loose phrasing the rules miss ("a couple of rowhouses without going before the zoning board" → 2 townhomes, by-right only). What the rules know can't be a filter (places outside the city, school quality, rentals, ADUs) is always added to "not understood", even if the model leaves it out. Strict tool use was tried and dropped: the API rejects the SearchFilters schema as too complex.

---

## 7. Known limitations

1. Construction cost is a placeholder and drives most verdicts.
2. Zoning Board data starts in 2025 (202 decisions, 28 denials); administrator exceptions and
   subdivisions use expert guesses.
3. Score weights are not yet calibrated against real outcomes.
4. Zoning covers the City of Pittsburgh only; slope and mine maps stop at the city line.
5. Zoning Board cases show case numbers only, no links to decisions (they name applicants).
6. Hazard overlays on the map, saved sites and editable assumptions are not in the UI.

---

## 8. Lots worth knowing for the demo

| Lot | Situation | Result |
|---|---|---|
| 52-H-93, Kentucky Ave | Clean lot | 62, feasible with conditions; 4-unit walk-up by right; a 6-unit walk-up with a variance, 2 similar board cases in the evidence drawer |
| 55-A-137, Bristol St | Steep slope | 40, high risk; 84% of the lot steep; 5 board cases nearby, none similar |
| 4-A-303 | Old mines | 55, feasible with conditions; mine investigation required |
| 129-J-37 | Needs an approval | 56; lot smaller than the minimum, administrator exception |
| 80-N-159 | Flood zone | 48, high risk |
| 24-J-60 | Two zoning districts | 48, high risk, low confidence |
| 173-E-82 | City-owned lot | 61, feasible with conditions |
| 176-C-275 | Outside the city | Not scored; partial report |

Other lots with one similar board case: 56-C-74, 56-C-71, 56-K-290, 56-G-90, 56-D-184.
All of these are in the served bundle. Open 52-H-93 from the search box, not from a
building-type search: a search like "2 townhomes" re-scores the lot and the approvals option
can change.
