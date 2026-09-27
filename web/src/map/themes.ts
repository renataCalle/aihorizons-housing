/**
 * Map themes: the basemap's colours, whether the 3D view raises buildings, and the score band
 * colours. The one source for these colours: the map layers read them from here, and the UI
 * (legend, list dots, pills, report) reads the same values as CSS variables set on the root
 * (applyThemeVariables). tokens.css repeats Blueprint's values as the first-paint default.
 */
import { BLUEPRINT, STANDARD, type BasemapPalette } from './blueprintTheme'

export type MapThemeId = 'blueprint' | 'standard'

export interface BandColors {
  fast: string
  conditions: string
  /** Strong risk: the report, and the lot whose report is open */
  risk: string
  /** Soft risk: high-risk lots on the map and in search results */
  riskSoftFill: string
  riskSoftOutline: string
  /** Unknown lots are hatched: `unknownLine` stripes on `unknownTint` */
  unknownLine: string
  unknownTint: string
}

export interface MapTheme {
  id: MapThemeId
  label: string
  basemap: BasemapPalette
  /** Lot lines between lots that aren't candidates */
  lotLine: string
  /** The 3D view raises the basemap's buildings */
  buildings3d: boolean
  bands: BandColors
}

const SOFT_RISK = { riskSoftFill: '#F9BE8C', riskSoftOutline: '#D9480F' }
const UNKNOWN = { unknownLine: '#8C9BB5', unknownTint: '#F1F4F9' }

export const THEMES: Record<MapThemeId, MapTheme> = {
  blueprint: {
    id: 'blueprint',
    label: 'Blueprint',
    basemap: {
      ...BLUEPRINT,
      land: '#F1F4F8',
      park: '#E3EAF0',
      wood: '#E3EAF0',
      water: '#CFDCEA',
      waterLine: '#B8CADF',
      building: '#E6ECF3',
      buildingLine: '#D3DCE8',
      road: '#FFFFFF',
      roadCasing: '#C9D3E0',
    },
    lotLine: '#C9D3E0',
    buildings3d: false,
    bands: {
      fast: '#1B3FD1',
      conditions: '#6E9BF2',
      risk: '#E8590C',
      ...SOFT_RISK,
      ...UNKNOWN,
    },
  },
  standard: {
    id: 'standard',
    label: 'Standard',
    basemap: STANDARD,
    lotLine: '#D6D0C4',
    buildings3d: true,
    bands: {
      fast: '#1E3A8A',
      conditions: '#4F86E8',
      risk: '#E8590C',
      ...SOFT_RISK,
      ...UNKNOWN,
    },
  },
}

export const DEFAULT_THEME: MapThemeId = 'blueprint'

/** CSS variable for each band colour; tokens.css holds Blueprint's as the default. */
export const BAND_VARIABLES: Record<keyof BandColors, string> = {
  fast: '--band-fast-track',
  conditions: '--band-conditions',
  risk: '--band-high-risk',
  riskSoftFill: '--band-risk-soft-fill',
  riskSoftOutline: '--band-risk-soft-outline',
  unknownLine: '--band-unknown',
  unknownTint: '--band-unknown-tint',
}

/** Mark the root with the theme and expose its band colours to CSS. */
export function applyThemeVariables(theme: MapTheme, root: HTMLElement = document.documentElement) {
  root.dataset.mapTheme = theme.id
  for (const [key, variable] of Object.entries(BAND_VARIABLES)) {
    root.style.setProperty(variable, theme.bands[key as keyof BandColors])
  }
}

const STORAGE_KEY = 'pencil-it.map-theme'

/** The saved choice, or the default. Storage can be missing or blocked (private windows). */
export function loadThemeId(): MapThemeId {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return saved === 'blueprint' || saved === 'standard' ? saved : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

export function saveThemeId(id: MapThemeId) {
  try {
    window.localStorage.setItem(STORAGE_KEY, id)
  } catch {
    // Not saved: the choice still holds for this visit.
  }
}
