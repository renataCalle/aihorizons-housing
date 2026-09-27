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

  it('only the Standard theme raises buildings in 3D', () => {
    expect(THEMES.blueprint.buildings).toBeNull()
    expect(THEMES.standard.buildings?.roof).toMatch(HEX)
    expect(THEMES.standard.buildings?.tall).toMatch(HEX)
  })

  it('draws roofs in a different colour from the ground, so buildings keep their shape', () => {
    const roof = THEMES.standard.buildings?.roof.toLowerCase()
    expect(roof).not.toBe(THEMES.standard.basemap.land.toLowerCase())
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
