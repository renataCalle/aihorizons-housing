import type { Ref } from 'react'
import { Link } from 'react-router'
import { formatMaxLand, formatSqft } from '../lib/format'
import { approvalLabel, BAND_LABEL, programLabel, reliefType } from '../lib/labels'
import { spanOf } from '../models/estimate'
import type { Parcel } from '../models/report'
import type { ProgramFit } from '../models/search'
import { formatCountyId } from '../search/highlight'

interface Props {
  ref?: Ref<HTMLElement>
  parcel: Parcel
  fit: ProgramFit | null
  rank: number | null
  total: number
  /** The report link, carrying the search so "Back to N sites" returns to it. */
  reportHref: string
  onClose: () => void
}

/** The selected parcel, top right (SearchMap.dc.html). Every value is an engine or data field. */
export function InspectorCard({ ref, parcel, fit, rank, total, reportHref, onClose }: Props) {
  const band = parcel.band
  const path = fit
    ? `${approvalLabel(fit.outcome === 'by_right' ? [] : fit.reliefTypes)} · ${programLabel(fit.productType, fit.units)}`
    : parcel.leadOption
      ? `${approvalLabel(parcel.leadOption.relief.map(reliefType))} · ${programLabel(parcel.leadOption.productType, parcel.leadOption.units)}`
      : null

  return (
    <section ref={ref} className="inspector glass" aria-label={`Selected: ${parcel.name}`}>
      <span className="bracket bracket-tl" aria-hidden="true" />
      <span className="bracket bracket-br" aria-hidden="true" />
      <div className="inspector-head">
        <span className="label inspector-kicker">
          {rank ? `Selected · ${String(rank).padStart(2, '0')} / ${total}` : 'Selected'}
        </span>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <h2 className="inspector-title">{parcel.name}</h2>
      <p className="mono inspector-id">
        {formatCountyId(parcel.id)}
        {parcel.neighborhood && ` · ${parcel.neighborhood.toUpperCase()}`}
      </p>

      {band ? (
        <div className="inspector-score">
          <span className={`inspector-points band-${band}`}>
            {parcel.score ?? '—'}
            {parcel.score !== null && <small>/100</small>}
          </span>
          <span className={`band-pill pill-${band}`}>{BAND_LABEL[band]}</span>
        </div>
      ) : (
        <p className="inspector-none">Not a development candidate.</p>
      )}

      <dl className="inspector-rows">
        {path && (
          <div>
            <dt>Path</dt>
            <dd>{path}</dd>
          </div>
        )}
        {parcel.topFlag && (
          <div>
            <dt>Top risk</dt>
            <dd>
              <span className={`risk-dot risk-${parcel.topFlag.severity}`} aria-hidden="true" />
              {parcel.topFlag.title}
            </dd>
          </div>
        )}
        {parcel.maxLandPrice && (
          <div>
            <dt>Max land</dt>
            <dd>{formatMaxLand(spanOf(parcel.maxLandPrice))}</dd>
          </div>
        )}
        <div>
          <dt>Lot</dt>
          <dd>
            {formatSqft(parcel.lotAreaSqft)}
            {parcel.zoning.length > 0 && ` · ${parcel.zoning.join(', ')}`}
          </dd>
        </div>
      </dl>

      <Link className="button-primary inspector-open" to={reportHref}>
        Open full report
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </Link>
    </section>
  )
}
