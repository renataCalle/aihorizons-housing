import { create } from 'zustand'
import {
  applyThemeVariables,
  loadThemeId,
  saveThemeId,
  THEMES,
  type MapTheme,
  type MapThemeId,
} from '../map/themes'

interface MapThemeState {
  theme: MapTheme
  setTheme: (id: MapThemeId) => void
}

function show(theme: MapTheme) {
  if (typeof document !== 'undefined') applyThemeVariables(theme)
}

/** The map style (Blueprint or Standard), saved for the next visit. */
export const useMapTheme = create<MapThemeState>()((set) => {
  const theme = THEMES[loadThemeId()]
  show(theme)
  return {
    theme,
    setTheme: (id) => {
      saveThemeId(id)
      show(THEMES[id])
      set({ theme: THEMES[id] })
    },
  }
})
