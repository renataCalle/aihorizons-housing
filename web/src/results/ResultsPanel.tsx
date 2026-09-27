import { memo, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  BAND_LABEL,
  feasibilityLabel,
  programLabel,
  rankedForLabel,
  scoredLabel,
  SORT_LABEL,
} from '../lib/labels'
import { formatSqft } from '../lib/format'
import type { Filters, SortKey } from '../models/filters'
import type { Parcel } from '../models/report'
import type { FilterChip, ScoredProgram, SearchResponse } from '../models/search'
import { FilterEditor } from './FilterEditor'

interface Props {
  response: SearchResponse | null
  loading: boolean
  error: string | null
  filters: Filters
  onFilters: (next: Filters) => void
  onRemoveChip: (key: string) => void
  selectedId: string | null
  hoveredId: string | null
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
  onRetry: () => void
  layers: ReactNode
  /** Map layers shown, so the legend lists only what's drawn */
  showTransit: boolean
  /** Lots / Area view switch */
  tabs: ReactNode
}

/** The left panel on the results screen (SearchMap.dc.html). */
export function ResultsPanel(props: Props) {
  const { response, loading, error, filters, onFilters, selectedId } = props
  const [editing, setEditing] = useState(false)
  const selectedRow = useRef<HTMLLIElement>(null)

  // Keep the selected row in view when it's picked on the map.
  useEffect(() => {
    selectedRow.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedId])

  const total = response?.total ?? 0
  // Ranked for the searched building type, else by each lot's best fit (the engine's pick).
  const rankedFor = response?.rankedFor ?? null
  const target = rankedFor
    ? `for ${rankedForLabel(rankedFor.type, rankedFor.units)}`
    : 'by best fit'
  const order = filters.sort === 'score_desc' ? '' : ` · ${SORT_LABEL[filters.sort].heading}`

  return (
    <aside className="results-panel glass" aria-label="Search results">
      {props.tabs}
      <div className="results-head">
        <h2 className="label results-count" aria-live="polite">
          {loading && !response
            ? 'Searching…'
            : `${total} ${total === 1 ? 'lot' : 'lots'} ranked ${target}${order}`}
        </h2>
        <label className="sort-menu">
          <span className="visually-hidden">Sort by</span>
          <span aria-hidden="true">Sort: {SORT_LABEL[filters.sort].menu} ▾</span>
          <select
            value={filters.sort}
            onChange={(e) => onFilters({ ...filters, sort: e.target.value as SortKey })}
          >
            {(Object.keys(SORT_LABEL) as SortKey[]).map((key) => (
              <option key={key} value={key}>
                {SORT_LABEL[key].menu}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="chips">
        {response?.chips.map((chip) => (
          <ChipButton key={chip.key} chip={chip} onRemove={props.onRemoveChip} />
        ))}
        <button
          type="button"
          className="edit-filters"
          aria-expanded={editing}
          onClick={() => setEditing((v) => !v)}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
            <circle cx="16" cy="7" r="2" />
            <circle cx="10" cy="17" r="2" />
          </svg>
          {editing ? 'Done' : 'Edit filters'}
        </button>
      </div>

      {response && response.notApplied.length > 0 && (
        <p className="results-note">
          Not applied yet (no data): {response.notApplied.map((c) => c.label).join(', ')}.
        </p>
      )}

      {editing ? (
        <FilterEditor filters={filters} onChange={onFilters} />
      ) : (
        <div className="results-body">
          {error && (
            <div className="results-empty" role="alert">
              <p>Couldn't load results: {error}</p>
              <button type="button" className="button-secondary" onClick={props.onRetry}>
                Try again
              </button>
            </div>
          )}
          {!error && loading && !response && <Skeleton />}
          {!error && response && response.total === 0 && (
            <div className="results-empty">
              <p>No sites match.</p>
              {response.suggestion && (
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => props.onRemoveChip(response.suggestion!.remove.key)}
                >
                  Remove “{response.suggestion.remove.label}” ({response.suggestion.wouldReturn}{' '}
                  {response.suggestion.wouldReturn === 1 ? 'site' : 'sites'})
                </button>
              )}
            </div>
          )}
          {response && response.results.length > 0 && (
            <ol className={loading ? 'results-list is-stale' : 'results-list'}>
              {response.results.map((r) => (
                <Row
                  key={r.parcel.id}
                  ref={r.parcel.id === selectedId ? selectedRow : undefined}
                  rank={r.rank}
                  parcel={r.parcel}
                  scored={r.scored}
                  selected={r.parcel.id === selectedId}
                  hovered={r.parcel.id === props.hoveredId}
                  onSelect={props.onSelect}
                  onHover={props.onHover}
                />
              ))}
            </ol>
          )}
          {response && response.nearMisses.length > 0 && (
            <>
              <h3 className="label results-subhead">Near misses · one filter away</h3>
              <ol className="results-list">
                {response.nearMisses.map((n) => (
                  <Row
                    key={n.parcel.id}
                    parcel={n.parcel}
                    note={`Fails: ${n.failed.label}`}
                    selected={n.parcel.id === selectedId}
                    hovered={n.parcel.id === props.hoveredId}
                    onSelect={props.onSelect}
                    onHover={props.onHover}
                  />
                ))}
              </ol>
            </>
          )}
        </div>
      )}

      <div className="results-foot">
        <Legend
          title={rankedFor ? feasibilityLabel(rankedFor.type) : 'Best fit'}
          showTransit={props.showTransit}
          showArea={filters.areas.length > 0}
        />
        {props.layers}
      </div>
    </aside>
  )
}

function ChipButton({ chip, onRemove }: { chip: FilterChip; onRemove: (key: string) => void }) {
  return (
    <button
      type="button"
      className="chip"
      aria-label={`Remove filter: ${chip.label}`}
      onClick={() => onRemove(chip.key)}
    >
      {chip.label}
      <span aria-hidden="true" className="chip-x">
        ×
      </span>
    </button>
  )
}

interface RowProps {
  ref?: React.Ref<HTMLLIElement>
  rank?: number
  parcel: Parcel
  /** What the lot is ranked on; near misses show the engine's pick */
  scored?: ScoredProgram | null
  note?: string
  selected: boolean
  hovered: boolean
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}

/**
 * One result. Memoized: with ~1,000 results, a hover or selection change re-renders only the
 * rows whose `selected` or `hovered` changed (the callbacks from MapScreen are stable).
 */
const Row = memo(function Row({
  ref,
  rank,
  parcel,
  scored,
  note,
  selected,
  hovered,
  onSelect,
  onHover,
}: RowProps) {
  const score = scored ? scored.score : parcel.score
  const band = (scored ? scored.band : parcel.band) ?? 'unknown'
  const lead = parcel.leadOption
  // Every score names the building it is for.
  const building = scored
    ? scoredLabel(scored)
    : lead
      ? programLabel(lead.productType, lead.units)
      : null
  const classes = ['result-row', selected && 'is-selected', hovered && 'is-hovered']
  return (
    <li ref={ref}>
      <button
        type="button"
        className={classes.filter(Boolean).join(' ')}
        aria-pressed={selected}
        onClick={() => onSelect(parcel.id)}
        onMouseEnter={() => onHover(parcel.id)}
        onMouseLeave={() => onHover(null)}
        onFocus={() => onHover(parcel.id)}
        onBlur={() => onHover(null)}
      >
        <span className="result-rank">{rank ? String(rank).padStart(2, '0') : '··'}</span>
        <span className={`swatch swatch-${band}`} aria-hidden="true" />
        <span className="result-main">
          <span className="result-name">{parcel.name}</span>
          <span className="result-meta">
            {note ??
              [building, formatSqft(parcel.lotAreaSqft).replace('sq ft', 'SF')]
                .filter(Boolean)
                .join(' · ')}
          </span>
        </span>
        <span className={`result-score band-${band}`}>
          <span className="result-points">
            {score ?? '—'}
            {score !== null && <small>/100</small>}
          </span>
          <span className="result-band">{BAND_LABEL[band]}</span>
        </span>
      </button>
    </li>
  )
})

function Skeleton() {
  return (
    <ol className="results-list" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <li key={i} className="result-row is-skeleton" />
      ))}
    </ol>
  )
}

function Legend(props: { title: string; showTransit: boolean; showArea: boolean }) {
  const { showTransit, showArea } = props
  return (
    <ul className="legend" aria-label={`Legend: ${props.title}`}>
      <li className="legend-title">{props.title}</li>
      <li>
        <span className="swatch swatch-fast_track" aria-hidden="true" />
        Fast
      </li>
      <li>
        <span className="swatch swatch-conditions" aria-hidden="true" />
        Conditions
      </li>
      <li>
        <span className="swatch swatch-high_risk" aria-hidden="true" />
        Risk
      </li>
      <li>
        <span className="swatch swatch-unknown" aria-hidden="true" />
        Unknown
      </li>
      {showTransit && (
        <li>
          <span className="swatch swatch-stop" aria-hidden="true" />
          Transit stop
        </li>
      )}
      {showArea && (
        <li>
          <span className="swatch swatch-area" aria-hidden="true" />
          Area searched
        </li>
      )}
    </ul>
  )
}
