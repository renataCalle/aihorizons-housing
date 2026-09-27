import { useId, useState } from 'react'
import { MapStyleSwitch } from '../map/MapStyleSwitch'
import { useMapTheme } from '../state/mapTheme'

/**
 * The map style, then overlays. Steep slope, undermining and flood layers need the pipeline's
 * geometry.
 */
export function LayersMenu({
  transit,
  onTransit,
}: {
  transit: boolean
  onTransit: (on: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const { theme, setTheme } = useMapTheme()
  const menuId = useId()
  return (
    <div className="layers">
      <button
        type="button"
        className="layers-button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 4l9 5-9 5-9-5 9-5z" />
          <path d="M3 14l9 5 9-5" />
        </svg>
        Layers
      </button>
      {open && (
        <div id={menuId} className="layers-menu glass">
          <MapStyleSwitch themeId={theme.id} onTheme={setTheme} />
          <label className="check">
            <input type="checkbox" checked={transit} onChange={(e) => onTransit(e.target.checked)} />
            Transit stops
          </label>
          {['Steep slope', 'Undermined areas', 'Flood zones'].map((name) => (
            <label key={name} className="check is-disabled" title="Needs the pipeline's map data">
              <input type="checkbox" disabled />
              {name}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
