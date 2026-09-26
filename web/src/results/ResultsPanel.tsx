import { useEffect, useRef, useState, type ReactNode } from 'react'
import { BAND_LABEL, SORT_LABEL } from '../lib/labels'
import { formatSqft } from '../lib/format'
import type { Filters, SortKey } from '../models/filters'
import type { Parcel } from '../models/report'
import type { FilterChip, SearchResponse } from '../models/search'
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
  const heading = SORT_LABEL[filters.sort].heading

  return (
    <aside className="results-panel glass" aria-label="Search results">
      <div className="results-head">
        <h2 className="label results-count" aria-live="polite">
          {loading && !response ? 'Searching…' : `${total} ${total === 1 ? 'site' : 'sites'} · ${heading}`}
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
        <Legend />
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
  note?: string
  selected: boolean
  hovered: boolean
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}

function Row({ ref, rank, parcel, note, selected, hovered, onSelect, onHover }: RowProps) {
  const band = parcel.band ?? 'unknown'
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
              [parcel.zoning.join(', '), formatSqft(parcel.lotAreaSqft).replace('sq ft', 'SF')]
                .filter(Boolean)
                .join(' · ')}
          </span>
        </span>
        <span className={`result-score band-${band}`}>
          <span className="result-points">{parcel.score ?? '—'}</span>
          <span className="result-band">{BAND_LABEL[band]}</span>
        </span>
      </button>
    </li>
  )
}

function Skeleton() {
  return (
    <ol className="results-list" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <li key={i} className="result-row is-skeleton" />
      ))}
    </ol>
  )
}

function Legend() {
  return (
    <ul className="legend" aria-label="Legend">
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
    </ul>
  )
}
