import type { Ref } from 'react'
import { Link } from 'react-router'
import { formatMaxLand, formatSqft } from '../lib/format'
import { approvalLabel, BAND_LABEL, programLabel, reliefType, scoredLabel } from '../lib/labels'
import { spanOf } from '../models/estimate'
import type { Parcel } from '../models/report'
import type { ProgramFit, ScoredProgram } from '../models/search'
import { formatCountyId } from '../search/highlight'

interface Props {
  ref?: Ref<HTMLElement>
  parcel: Parcel
  fit: ProgramFit | null
  /** What the lot is ranked on in this search; null = show the engine's pick */
  scored: ScoredProgram | null
  /** The engine's pick when the lot is scored on another building type */
  betterFit: ScoredProgram | null
  rank: number | null
  total: number
  /** The report link, carrying the search so "Back to N sites" returns to it. */
  reportHref: string
  onClose: () => void
}

/** The selected parcel, top right (SearchMap.dc.html). Every value is an engine or data field. */
export function InspectorCard(props: Props) {
  const { ref, parcel, fit, scored, betterFit, rank, total, reportHref, onClose } = props
  const band = scored ? scored.band : parcel.band
  const score = scored ? scored.score : parcel.score
  const maxLand = scored ? scored.maxLandPrice : parcel.maxLandPrice
  const path = pathLabel(parcel, fit, scored)

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
            {score ?? '—'}
            {score !== null && <small>/100</small>}
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
        {maxLand && (
          <div>
            <dt>Max land</dt>
            <dd>{formatMaxLand(spanOf(maxLand))}</dd>
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

      {betterFit && (
        <p className="inspector-better">
          Better fit on this lot: {scoredLabel(betterFit)}
          {betterFit.score !== null && ` · ${betterFit.score}`}
        </p>
      )}

      <Link className="button-primary inspector-open" to={reportHref}>
        Open full report
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </Link>
    </section>
  )
}

/** "Special exception + Variance · Up to 2 townhomes": the approvals, then the building. */
function pathLabel(parcel: Parcel, fit: ProgramFit | null, scored: ScoredProgram | null) {
  if (scored) {
    if (!scored.productType) return null
    const approvals =
      scored.outcome === 'rejected' ? 'Not allowed' : approvalLabel(scored.reliefTypes)
    return `${approvals} · ${scoredLabel(scored)}`
  }
  if (fit) {
    const approvals = approvalLabel(fit.outcome === 'by_right' ? [] : fit.reliefTypes)
    return `${approvals} · ${programLabel(fit.productType, fit.units)}`
  }
  const lead = parcel.leadOption
  if (!lead) return null
  const approvals = approvalLabel(lead.relief.map(reliefType))
  return `${approvals} · ${programLabel(lead.productType, lead.units)}`
}
