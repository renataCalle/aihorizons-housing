import { THEMES, type MapThemeId } from './themes'

/** "Blueprint | Standard": a segmented control of real buttons, one pressed. */
export function MapStyleSwitch({
  themeId,
  onTheme,
}: {
  themeId: MapThemeId
  onTheme: (id: MapThemeId) => void
}) {
  return (
    <div className="style-switch" role="group" aria-label="Map style">
      {Object.values(THEMES).map((theme) => (
        <button
          key={theme.id}
          type="button"
          className="style-switch-option"
          aria-pressed={theme.id === themeId}
          onClick={() => onTheme(theme.id)}
        >
          {theme.label}
        </button>
      ))}
    </div>
  )
}
