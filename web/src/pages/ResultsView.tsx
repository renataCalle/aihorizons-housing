import { useRef } from 'react'
import { fetchSiteReport } from '../api'
import { removeChip } from '../api/adapters'
import { useAsync } from '../lib/useAsync'
import { LeaderLine } from '../map/SearchOverlays'
import { InspectorCard } from '../results/InspectorCard'
import { LayersMenu } from '../results/LayersMenu'
import { ResultsPanel } from '../results/ResultsPanel'
import { useMapScreen } from './mapScreenContext'

/** /search: the results panel and the inspector card over the map (docs/01, §3). */
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

  return (
    <>
      {s.filters && (
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
          layers={<LayersMenu transit={s.transit} onTransit={s.setTransit} />}
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
