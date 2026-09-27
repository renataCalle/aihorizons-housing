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

Base (MapLibre GL JS 6, already in `web/package.json`): **OpenFreeMap Positron** (`https://tiles.openfreemap.org/styles/positron`), recolored at load time by `applyMapTheme(style, palette)` in `web/src/map/blueprintTheme.ts`, which walks the style's layers and overrides paint properties.

**Two map themes (Sep 2026): Blueprint (default) and Standard.** Viewers switch with "Blueprint | Standard" at the top of the Layers menu or the style button in the map controls; the choice is saved in `localStorage`. Switching recolours the live map (no reload: data layers, selection and camera stay). Every colour lives in `web/src/map/themes.ts`, the one source: the map reads it directly, and the UI reads the band colours as CSS variables set on the root with `data-map-theme` (`tokens.css` repeats Blueprint's as the first-paint default; a test keeps them equal).

| Layer group | Blueprint (default) | Standard (sampled from Mapbox "Standard" day) |
|---|---|---|
| background, landuse | `#F1F4F8` | `#F0ECE2` |
| parks, grass | `#E3EAF0` (grass layer added: Positron has none) | `#BEE8B2` |
| woods | `#E3EAF0` | `#B4E0A7` |
| water | `#CFDCEA`, outline `#B8CADF` | `#A7DAFA`, outline `#97CFF3` |
| buildings | fill `#E6ECF3`, outline `#D3DCE8` | fill `#E4E0D7`, outline `#D8D4CC` |
| roads | `#FFFFFF`, casing `#C9D3E0` | `#BFC5D6`, casing `#B0B7CB` |
| lot lines (not candidates) | `#C9D3E0` | `#D6D0C4` |
| labels | `#6A84B8`, letter-spaced uppercase for places; hide POI icons | same style in `#56657E` |
| 3D buildings | hidden | raised to mapped heights |

**Score bands** (fill opacity 0.85, thin white line between adjacent lots):

| Band | Blueprint | Standard |
|---|---|---|
| Fast track | `#1B3FD1` | `#1E3A8A` |
| With conditions | `#6E9BF2` | `#4F86E8` |
| High risk, strong (the report, and the lot whose report is open) | `#E8590C` | `#E8590C` |
| High risk, soft (the map and search results) | fill `#F9BE8C`, 1.5px outline `#D9480F` | same |
| Unknown | hatched `#8C9BB5` on `#F1F4F9` | same |

Pills keep text at 4.5:1 or better: fast track is white on the band colour; with conditions and soft risk use tints of their band with the band colour as border.

Add a technical grid feel with a faint 48px grid as a CSS background behind a slightly transparent basemap, or skip it if it hurts performance.

**Data layers** (from `GET /api/map/parcels`):
1. `parcels-fill`: fill by `band` using the theme's band colours at 0.85 opacity; unknown uses a hatch pattern image (`map.addImage` of a 6px diagonal pattern). Lots that aren't candidates have no fill, outline only.
2. `parcels-outline`: white 0.75px between scored lots, the soft risk outline on high-risk lots, the theme's lot line for the rest; selected parcel `#0B1B3F`, 2.5px.
3. `area-dim`: a polygon of the world minus the searched neighborhoods, fill `#F5F8FD` at 0.66 opacity.
4. `area-boundary`: dashed cobalt line, 1.5px, with a mono label chip.
5. `rank-tags`: symbol layer with rank numbers for the top results (or HTML markers).
6. `transit-stops`: white circles with a cobalt stroke (Layers toggle).
7. Crosshair: an HTML marker on the selected parcel's centroid.

**Terrain:** tried in 3D (AWS Terrain Tiles, Terrarium) and dropped: lots draped over hillsides read poorly.

**3D view (built, replaces the score view below):** the "3D" control (`view=3d` in the URL) tilts the camera to 66° at street level and raises the basemap's buildings to their mapped heights in the Standard theme (OpenMapTiles `render_height`, MapLibre `fill-extrusion`): cream `#E9E5DC` for houses, glassy blue `#9EB7CD` for towers, solid and always drawn above the lots. Blueprint shows no buildings in 3D. Lots stay coloured by band on the ground. Sky and horizon haze via MapLibre's sky.

*Original plan, not built:* deck.gl extruded parcels, elevation = score scaled, fill by band, pitch about 55°, bearing about −30°, with a glow under fast-track parcels.

## Icons

Inline stroke SVG (Tabler or Lucide style), 1.8–2px stroke, never emoji.
