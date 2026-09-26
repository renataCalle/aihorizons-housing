# 02 · Design system and map style

The look is **light blueprint**: pale sky-blue map, cobalt as the single strong color, thin technical linework, small mono labels, and frosted-glass panels floating over a full-screen map. Orange is reserved for risk. The exact values below come from the mockups in `docs/design/source/`.

## Color tokens

Define these as CSS custom properties in one place (`web/src/styles/tokens.css`).

| Token | Value | Use |
|---|---|---|
| `--ink` | `#0B1B3F` | Primary text |
| `--ink-2` | `#3E4F6E` | Body text on white |
| `--ink-3` | `#4A5B7A` | Secondary text, mono labels |
| `--ink-4` | `#5E6E8A` | Captions (12px+ only) |
| `--cobalt` | `#1D3FD6` | Brand, fast track, primary buttons, links |
| `--cobalt-deep` | `#1530A8` | Text on cobalt tints, hover |
| `--cobalt-tint` | `#E7EEFF` | Chips, selected tints |
| `--cobalt-tint-2` | `#EEF3FF` | Verdict card background |
| `--cobalt-line` | `#C9D6FB` | Borders on cobalt tints |
| `--sky` | `#8DB4F5` | "With conditions" band |
| `--orange` | `#F07A1A` | "High risk" band, risk dots |
| `--orange-text` | `#A8480B` | Text on orange tints |
| `--orange-tint` | `#FFF4EB` | Caution pill background |
| `--orange-line` | `#F6C39A` | Caution pill border |
| `--unknown` | `#8C9BB5` | Hatch lines for unknown |
| `--unknown-tint` | `#F1F4F9` | Unknown pill background |
| `--paper` | `#EEF4FB` | Map land, app background |
| `--panel` | `#FBFCFF` | Report panel background |
| `--line` | `#DCE5F5` | Card borders |
| `--line-soft` | `#EAF0FA` | Row dividers |

### Bands (map fills and swatches)

| Band | Fill | Second cue |
|---|---|---|
| Fast track | `--cobalt` | Solid, darkest |
| With conditions | `--sky` | Solid, lighter |
| High risk | `--orange` | Different hue and lightness |
| Unknown | Hatched `--unknown` on `--unknown-tint` | Hatching |
| Not a candidate | No fill, outline `#C5D7EF` | Outline only |

### Severity pills

- **Deal risk:** solid `--orange` background, white text, ✕ icon.
- **Caution:** `--orange-tint` background, `--orange-line` border, `--orange-text` text, ⚠ icon.
- **Unknown:** `--unknown-tint` background, dashed `--unknown` border, `--ink-2` text, ? icon.
- **Cleared:** `--cobalt` check icon on `#F3F7FF`.

## Glass panels

```css
.glass {
  background: rgba(255, 255, 255, 0.74);
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  box-shadow: 0 0 0 1px rgba(29, 63, 214, 0.08), 0 12px 36px rgba(11, 27, 63, 0.10);
}
```

Use glass for everything floating on the map (top bar, left panel, inspector, controls, readouts). The report panel and evidence drawer are solid (`--panel`, white) for reading comfort.

The inspector card has two small cobalt corner brackets (top-left and bottom-right, 10px, 1.5px stroke) as a blueprint detail.

## Typography

- **Sora** (Google Fonts, 300–700): all UI text, headings and big numbers. Headings use `letter-spacing: -0.01em` to `-0.03em`.
- **IBM Plex Mono** (400, 500): parcel IDs, codes, coordinates, and small uppercase labels with `letter-spacing: 0.12em`–`0.16em`.

| Style | Font | Size / weight |
|---|---|---|
| Landing headline | Sora | 46 / 600 |
| Report title | Sora | 28 / 600 |
| Verdict sentence | Sora | 22 / 500 |
| Section heading | Sora | 20 / 600 |
| Big score | Sora | 48–68 / 600, cobalt |
| Body | Sora | 13–15 / 400 |
| Label | Plex Mono | 10–11 / 400, uppercase |

## Shape and spacing

Radii: 8 (chips), 10–12 (buttons, inputs), 14–16 (cards, rows), 20 (panels), 999 (pills). Spacing scale: 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32. Minimum touch target 44px for primary controls.

## Blueprint details

Use these sparingly; they carry the style:
- Numbered mono section labels (`01 — WHAT TO BUILD`).
- Dashed lines with dot ends for leaders and the scale bar.
- A crosshair marker on the selected parcel: dashed ring r=30, a faint outer ring r=44, four short tick lines.
- Brand mark: a four-point star inside a dashed circle, in cobalt.

## Map style

Base (MapLibre GL JS 6, already in `web/package.json`): **OpenFreeMap Positron** (`https://tiles.openfreemap.org/styles/positron`), recolored at load time. Write one function, `applyBlueprintTheme(style)`, that walks the style's layers and overrides paint properties:

| Layer group | Paint |
|---|---|
| background, landuse, park | `#EEF4FB` (parks one step lighter, no green) |
| water | `#D3E3F7`, outline `#B4CCEC` |
| buildings | fill `#E3ECF8`, outline `#C5D7EF` |
| roads (minor) | `#FFFFFF` |
| roads (major) | `#FFFFFF`, casing `#D5E2F4` |
| rail, paths | `#C9D9F0`, dashed |
| labels | Plex Mono–like letter-spaced uppercase in `#6A84B8` for places; hide POI icons |

Add a technical grid feel with a faint 48px grid as a CSS background behind a slightly transparent basemap, or skip it if it hurts performance.

**Data layers** (from `GET /api/map/parcels`):
1. `parcels-fill`: fill by `band` using the band colors; unknown uses a hatch pattern image (`map.addImage` of a 6px diagonal pattern).
2. `parcels-outline`: `#C5D7EF`, 0.8px; selected parcel `#0B1B3F`, 2.5px.
3. `area-dim`: a polygon of the world minus the searched neighborhoods, fill `#F5F8FD` at 0.66 opacity.
4. `area-boundary`: dashed cobalt line, 1.5px, with a mono label chip.
5. `rank-tags`: symbol layer with rank numbers for the top results (or HTML markers).
6. `transit-stops`: white circles with a cobalt stroke (Layers toggle).
7. Crosshair: an HTML marker on the selected parcel's centroid.

**Terrain (stretch):** hillshade from AWS Terrain Tiles (Terrarium encoding), tinted blue, low opacity, so Pittsburgh's slopes read on the map.

**3D score view:** deck.gl rendered interleaved with MapLibre through deck.gl's MapLibre overlay (check the deck.gl "Using with MapLibre" page for the current package name and MapLibre 6 support; in React, mount it with react-map-gl's `useControl`). A `PolygonLayer` with `extruded: true`, elevation = score scaled, fill by band, pitch about 55°, bearing about −30°. Glow: a `ScatterplotLayer` with large radius and low alpha under fast-track parcels.

## Icons

Inline stroke SVG (Tabler or Lucide style), 1.8–2px stroke, never emoji.
