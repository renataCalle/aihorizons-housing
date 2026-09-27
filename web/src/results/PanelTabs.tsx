/**
 * The left panel's two views of one search: the ranked lots (for a developer picking a site)
 * and the area view (for a planner asking what holds the area back).
 */
export function PanelTabs({ areaView, onAreaView }: { areaView: boolean; onAreaView: (on: boolean) => void }) {
  return (
    <div className="panel-tabs" role="group" aria-label="Panel view">
      <button type="button" aria-pressed={!areaView} onClick={() => onAreaView(false)}>
        Lots
      </button>
      <button type="button" aria-pressed={areaView} onClick={() => onAreaView(true)}>
        Area view
      </button>
    </div>
  )
}
