import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  applyThemeVariables,
  BAND_VARIABLES,
  DEFAULT_THEME,
  loadThemeId,
  THEMES,
  type BandColors,
} from './themes'

const HEX = /^#[0-9a-f]{6}$/i

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const BAND_KEYS: (keyof BandColors)[] = [
  'fast',
  'conditions',
  'risk',
  'riskSoftFill',
  'riskSoftOutline',
  'unknownLine',
  'unknownTint',
]

describe('map themes', () => {
  it.each(Object.values(THEMES))('$label defines every band colour', (theme) => {
    expect(Object.keys(theme.bands).sort()).toEqual([...BAND_KEYS].sort())
    for (const key of BAND_KEYS) expect(theme.bands[key]).toMatch(HEX)
    for (const colour of Object.values(theme.basemap)) expect(colour).toMatch(HEX)
    expect(theme.lotLine).toMatch(HEX)
  })

  it('exposes every band colour as a CSS variable', () => {
    expect(Object.keys(BAND_VARIABLES).sort()).toEqual([...BAND_KEYS].sort())
  })

  it("keeps tokens.css's first-paint defaults equal to the default theme", () => {
    const css = readFileSync(new URL('../styles/tokens.css', import.meta.url), 'utf8')
    for (const [key, variable] of Object.entries(BAND_VARIABLES)) {
      const match = css.match(new RegExp(`${variable}:\\s*(#[0-9a-f]{6})`, 'i'))
      expect(match?.[1].toLowerCase(), variable).toBe(
        THEMES[DEFAULT_THEME].bands[key as keyof BandColors].toLowerCase(),
      )
    }
  })

  // Contrast of a roof (drawn at full light) with the ground. 1.07 is the roof that lost its
  // shape on the cream ground; 1.15 keeps buildings readable.
  it.each(Object.values(THEMES))('$label buildings stand apart from the ground', (theme) => {
    const b = theme.buildings
    expect(b).not.toBeNull()
    for (const colour of [b!.low, b!.high]) {
      expect(colour).toMatch(HEX)
      expect(contrast(colour, theme.basemap.land), colour).toBeGreaterThanOrEqual(1.15)
    }
    expect(b!.light).toBeGreaterThan(0)
  })

  it('falls back to the default theme when storage is unavailable', () => {
    expect(loadThemeId()).toBe(DEFAULT_THEME)
  })

  it('marks the root and sets the band variables', () => {
    const vars = new Map<string, string>()
    const root = {
      dataset: {} as Record<string, string>,
      style: { setProperty: (k: string, v: string) => vars.set(k, v) },
    }
    applyThemeVariables(THEMES.standard, root as unknown as HTMLElement)
    expect(root.dataset.mapTheme).toBe('standard')
    expect(vars.get('--band-fast-track')).toBe(THEMES.standard.bands.fast)
    expect(vars.get('--band-risk-soft-fill')).toBe(THEMES.standard.bands.riskSoftFill)
  })
})
