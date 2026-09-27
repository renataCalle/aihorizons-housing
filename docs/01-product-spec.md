# 01 · Product spec

## The one question

The product answers one question for a small infill developer: **should I spend money on this site, and if so, on what?** Today they pay consultants for a first-pass zoning read, a rough test fit and a back-of-envelope pro forma, and most sites die at that stage anyway. This tool does the first pass in under a minute and says which paid studies are worth commissioning, in what order.

**Persona.** A small developer (2–10 people) doing 3–20 unit projects in Pittsburgh. Comfortable with pro formas, not a zoning lawyer. Screens sites on a laptop between other things.

**Coverage.** Zoning rules cover the City of Pittsburgh only. A parcel outside city limits gets a partial report labeled "Zoning not covered for [municipality]".

## Screens

The mockups for every screen are in `docs/design/screens/`, and the exact markup is in `docs/design/source/`. The table maps each screen to its source file.

| # | Screen | Source file | Route |
|---|---|---|---|
| 1 | Landing | `Landing.dc.html` | `/` |
| 2a | Search box: typing a parcel ID | `SearchTyping.dc.html` | overlay on `/` |
| 2b | Search box: describing a site (AI) | `SearchAsk.dc.html` | overlay on `/` |
| 3 | Results | `SearchMap.dc.html` (uses `MapBase.dc.html`) | `/search?q=…` |
| 4 | Report open | `ReportOpen.dc.html` (uses `ReportPanel.dc.html`) | `/parcel/:id` |
| 5 | Evidence drawer | `EvidenceOpen.dc.html` | `/parcel/:id/evidence/:evidenceId` |
| — | 3D score view | `ScoreView3D.dc.html` | `/search?q=…&view=3d` |

Routes are deep-linkable so a developer can share a report or a search.

### 1 · Landing

Full-screen city map, calm and slightly faded. Brand top-left, "Saved sites" top-right. Center: a small mono label, the headline "What can you build here?", one subtitle line, and **one search box**. Under the box, three example chips (a parcel ID, an address, an AI prompt) and a hint: "or click any lot on the map". Nothing else. No mode toggle.

### 2 · The search box ("omnibox")

One box handles everything. It detects the input type as the user types:

| Input | Detection | Behavior |
|---|---|---|
| Parcel ID | The county parcel ID, dashed or compact (`0088-B-00044-0000-00`, `0088B00044000000`), or the city block-lot (`16-E-25`). Partial county IDs count after 6+ characters. | Dropdown shows matching parcels with score and band. Enter opens the report. Never sent to the AI. |
| Address | Starts with a house number and includes a street suffix (`3525 Beechwood Blvd`). "3 townhomes in Hazelwood" is not an address. | Dropdown shows address matches. Enter opens the report. Never sent to the AI. |
| Anything else | Description | Debounced call to `POST /api/search/parse`. The dropdown shows "How we read it" as editable chips, the phrase-to-filter readings, anything not understood, and a primary "Show N matching sites" button. |

The box shows a small "Detected: parcel ID" or "AI search" tag so the user always knows which mode they're in. Keyboard: Enter, ↑↓, Esc, Tab to move into the chips.

### 3 · Results

Map-first layout:

- **Top bar (glass):** brand (links to landing), the search box showing the current query with an AI tag and a clear button, "Illustrative data" badge, "Saved sites".
- **Left panel (glass, 360px):** "14 SITES · BEST FIRST" and a sort menu; the active filter chips (each removable) plus "Edit filters", which opens the full filter controls; the ranked list; a one-line legend and a "Layers" button.
- **Map:** parcels colored by band for the chosen product. Non-candidates get only an outline. The searched neighborhoods get a dashed boundary, and the rest of the city is dimmed. Rank tags (01, 02 …) sit on the top results. The selected parcel gets a crosshair marker and a dashed leader line to the inspector card.
- **Inspector card (glass, 300px, top-right):** "SELECTED · 01 / 14", name and ID, big score and band pill, path, top risk, max land price, lot, and "Open full report".
- **Bottom:** coordinate and scale readout; map controls (3D, zoom in/out).

The list and the map stay in sync: hovering a row highlights its parcel, and clicking a parcel selects its row.

**Edit filters** opens the full controls inside the left panel: product type and units, areas, approval paths, max land price, lot size, flat lots, near transit, owner type, exclude constraints, include unknowns, assemblies, near misses. The chips, the controls and AI search all read and write the same `SearchFilters` state.

**Layers** toggles overlays: steep slope, undermined areas, flood zones, transit stops.

### 4 · Report

Opens as a 720px panel on the right. The map shifts so the selected parcel stays visible, and a "Back to 14 sites" pill appears top-left. Panel sections, top to bottom:

1. Header: "SITE REPORT · 01 / 14", Save, Export memo, close. Title, ID line, "Illustrative data" badge.
2. Verdict card: band pill, the headline sentence (from the API; no numbers composed in the frontend), the big score with its p10–p90 range, "Where the score comes from" (one bar per score component the engine returns).
3. Three headline numbers: approval path (with the approval probability range if the engine provides one), constraint cost premium, max land price at target margin (compared with the listed or assessed price). All ranges are p10–p90.
4. "What could kill this deal": findings worst first, each with severity pill, detail, source chip, confidence, impact, and "Evidence →". A "Cleared" line lists the checks that came back clean.
5. "What you can build": best by-right and best with approvals, each with margin, time to permit-ready, approvals and the code basis. The approvals option links to its evidence.
6. "What to check next": ordered steps with who, cost and time.
7. Footer: screening disclaimer, rules version, data date.

**Export memo** uses a print stylesheet of the report (two pages, sources appendix). No separate PDF component.

### 5 · Evidence drawer

A 580px drawer over the report. For zoning relief it shows: what the code requires (section, date, plain-language summary, link to the code on eCode360), similar cases nearby (granted count, median months, table of the closest cases with outcome pills), a note that an AI model extracted the cases from decision PDFs with a link per case, a confidence note, and "How to resolve".

### 3D score view (wow layer)

Opened from the "3D" map control. Isometric view of the searched neighborhood with candidate parcels extruded by score and colored by band, a soft glow under fast-track parcels, and a tooltip on the selected parcel. Left panel: "Hazelwood at a glance" with counts per band, "What holds sites back" bars, and a near-misses card. A "2D map / 3D score" toggle returns to the map.

## States every screen needs

- **Loading:** skeleton rows in the list; a short checklist of checks in the report panel while it loads.
- **Empty:** "No sites match. Try removing [the most restrictive filter]." with a one-click remove.
- **Error:** plain message plus retry. AI search failure falls back to the rule-based parser silently and shows a small "basic search" tag.
- **Outside city:** partial report with the coverage label.
- **Unknown data:** unknown findings and hatched parcels, never hidden.

## Copy rules

- Sentence case everywhere. Mono uppercase only for small labels (`14 SITES · BEST FIRST`).
- Screening language: "by-right under the zoning code as of Sep 2026", never "approved" or "compliant".
- Money as ranges: "$24k–$41k". Time as ranges: "5–7 months".
- "Free" instead of "$0" for no-cost steps.

## Out of scope for v1

Accounts and teams, a chat interface, planner mode, editing parcels, saved-search alerts, mobile layout beyond not breaking.
