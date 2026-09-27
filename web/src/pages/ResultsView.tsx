import { useRef } from 'react'
import { fetchAreaSummary, fetchSiteReport } from '../api'
import { removeChip } from '../api/adapters'
import { encodeFilters } from '../lib/filterUrl'
import { useAsync } from '../lib/useAsync'
import { LeaderLine } from '../map/SearchOverlays'
import { GlancePanel } from '../results/GlancePanel'
import { InspectorCard } from '../results/InspectorCard'
import { LayersMenu } from '../results/LayersMenu'
import { PanelTabs } from '../results/PanelTabs'
import { ResultsPanel } from '../results/ResultsPanel'
import { useMapScreen } from './mapScreenContext'

/** /search: the results panel (or the area view) and the inspector card over the map (docs/01, §3). */
export function ResultsView() {
  const s = useMapScreen()
  const cardRef = useRef<HTMLElement>(null)
  const { response, selectedId } = s

  const result = response?.results.find((r) => r.parcel.id === selectedId)
  const nearMiss = response?.nearMisses.find((n) => n.parcel.id === selectedId)
  const known = result?.parcel ?? nearMiss?.parcel
  const fetched = useAsync(selectedId && !known ? `sel:${selectedId}` : 'none', (signal) =>
    selectedId && !known ? fetchSiteReport(selectedId, signal) : Promise.resolve(null),
  )
  const selected = known ?? (fetched.status === 'ready' ? fetched.data?.parcel : null) ?? null

  // The area view sums up the searched lots; the ranked list is the other tab.
  const areaView = s.areaView
  const summary = useAsync(
    areaView && s.filters ? `glance:${encodeFilters(s.filters)}` : 'none',
    (signal) => (areaView && s.filters ? fetchAreaSummary(s.filters, signal) : Promise.resolve(null)),
  )
  const layers = <LayersMenu transit={s.transit} onTransit={s.setTransit} />
  const tabs = <PanelTabs areaView={areaView} onAreaView={s.setAreaView} />

  return (
    <>
      {s.filters && areaView && (
        <GlancePanel
          areas={s.filters.areas}
          summary={summary.status === 'ready' ? summary.data : null}
          loading={summary.status === 'loading'}
          error={summary.status === 'error' ? summary.error.message : null}
          tabs={tabs}
          onShowNearMisses={() =>
            s.filters && s.setAreaView(false, { ...s.filters, showNearMisses: true })
          }
          layers={layers}
        />
      )}
      {s.filters && !areaView && (
        <ResultsPanel
          response={response}
          loading={s.searchStatus === 'loading'}
          error={s.searchError}
          filters={s.filters}
          onFilters={s.setFilters}
          onRemoveChip={(key) => s.filters && s.setFilters(removeChip(s.filters, key))}
          selectedId={selectedId}
          hoveredId={s.hoveredId}
          onSelect={s.select}
          onHover={s.setHoveredId}
          onRetry={s.retry}
          layers={layers}
          tabs={tabs}
          showTransit={s.transit}
        />
      )}
      {s.q && !s.filters && (
        <p className="results-panel glass label" role="status">
          {s.parsing === 'error' ? `Couldn't read that search: ${s.parseError}` : 'Reading your search…'}
        </p>
      )}
      {selected && (
        <>
          <InspectorCard
            ref={cardRef}
            parcel={selected}
            fit={result?.fit ?? null}
            scored={result?.scored ?? null}
            betterFit={result?.betterFit ?? null}
            rank={result?.rank ?? null}
            total={response?.total ?? 0}
            reportHref={`/parcel/${selected.id}${s.linkQuery ? `?${s.linkQuery}` : ''}`}
            onClose={() => s.select(null)}
          />
          <LeaderLine at={selected.centroid} cardRef={cardRef} />
        </>
      )}
    </>
  )
}
