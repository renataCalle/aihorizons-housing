# web/ — Buildable PGH front end

Read the root `CLAUDE.md` first: its contract invariants and boundary rules apply here too. This file adds what's specific to the web app.

## What to build

The map-first app designed in `docs/design/`: landing with one smart search box, AI search preview, results on a blueprint map, report panel, evidence drawer, and a 3D score view. Full spec: `docs/01-product-spec.md`. Look and feel: `docs/02-design-system.md`. Mockups: `docs/design/screens/*.png`, exact markup and styles in `docs/design/source/*.dc.html`.

## Stack (already scaffolded, keep it)

- React 19, Vite, TypeScript, oxlint (`npm run dev | build | lint`). CI runs `npm ci`, lint and build, so all three must pass.
- MapLibre GL JS 6 (already in package.json), through `react-map-gl/maplibre` or a thin wrapper component.
- deck.gl for the 3D score view only, through its MapLibre overlay (interleaved).
- React Router for deep links (`/`, `/search`, `/parcel/:id`, `/parcel/:id/evidence/:evidenceId`).
- State: one filters store (Zustand or React context) that the chips, the filter editor and AI search all read and write.
- Plain CSS with design tokens in `src/styles/tokens.css`. Fonts: Sora and IBM Plex Mono (Google Fonts).
- Replace the Vite starter (`App.tsx`, `App.css`, `assets/hero.png` etc.).

## Types

Generate TypeScript types from the API's OpenAPI schema (`openapi-typescript` against FastAPI's `/openapi.json`) into `src/api/types.gen.ts`. Never hand-write contract types. Regenerate after any contract change.

## Rendering rules

- **Render SiteAnalysis generically.** Flags, score components, assumptions and next steps are arrays: loop over them. A new flag type must not need a frontend change.
- **Ranges:** estimates arrive as p10/p50/p90. Show p10–p90 as the range ("$24k–$41k"); p50 can be a marker or tooltip.
- **Unknown is never clear:** unknown flags render with the dashed "Unknown" pill and hatched parcels.
- **Screening language only.** Never "approved" or "compliant".
- **Narrative text comes from the API.** Don't compose sentences with numbers in the frontend.
- When the data is mock (`illustrative` or a mock provider flag), show the "Illustrative data" badge.

## Accessibility

Color is never the only signal (bands differ in lightness and fill; pills have icon + text). Blue vs. orange, never red vs. green. Real buttons, links and labeled inputs; `aria-label` on icon-only buttons; 44px touch targets; 4.5:1 text contrast; full keyboard support in the search box (Enter, ↑↓, Esc, Tab).

## Done means

Each screen matches its PNG, `npm run lint` and `npm run build` pass, and the search box detection has unit tests (Vitest).

## Contracts are provisional

The data contracts and root CLAUDE.md are still changing. Components use our own
view models. All mapping from API types happens in one file, `src/api/adapters.ts`,
so contract changes only touch that file.