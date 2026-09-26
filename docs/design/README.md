# Design references

## `screens/`: exported mockups (add these)

Export each artboard from the Buildable PGH design canvas (Share › Export, PNG) and save it here with these names:

| File | Artboard |
|---|---|
| `01-landing.png` | 1 · Landing |
| `02a-search-typing-id.png` | 2a · Typing a parcel ID |
| `02b-search-ai.png` | 2b · Describing a site (AI) |
| `03-results.png` | 3 · Results |
| `04-report-open.png` | 4 · Report open |
| `05-evidence.png` | 5 · Evidence drawer |
| `06-3d-score-view.png` | Wow layer · 3D score view |
| `component-report-panel.png` | Component · Report panel, full length |
| `component-map.png` | Component · Blueprint map |

## `source/`: exact markup and styles

Each `.dc.html` file is the source of one artboard. They use a design-tool runtime, so they won't open as normal web pages, but the markup is plain HTML with inline styles: every color, size, radius, font and spacing is exact. Use them to match the look, not as code to copy into the app.

- `<dc-import name="MapBase">` means "this screen contains the MapBase component". The map is drawn as a static SVG in the mockup; the real app uses MapLibre (see `docs/02-design-system.md`).
- The 3D view is hand-drawn SVG in the mockup; the real app uses deck.gl.
- All data in the mockups is illustrative and matches `fixtures/`.
