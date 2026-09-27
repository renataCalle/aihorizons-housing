import {
  formatAssumption,
  formatAssumptionRange,
  formatDollars,
  sentenceCase,
} from '../lib/format'
import type { Analysis, Freshness, Parcel } from '../models/report'
import { formatCountyId } from '../search/highlight'

const words = (key: string) => key.replace(/_/g, ' ')

/** The parcel's facts and the pro forma assumptions behind the numbers. */
export function ParcelFacts({ parcel, analysis }: { parcel: Parcel; analysis: Analysis | null }) {
  const dims = analysis?.lotDimensionsFt
  const facts: [string, string][] = [
    ['Parcel ID', formatCountyId(parcel.id)],
    ['Block-lot', parcel.blockLot ?? '—'],
    [
      'Lot',
      `${Math.round(parcel.lotAreaSqft).toLocaleString('en-US')} sq ft` +
        (dims ? ` (${Math.round(dims.width)} × ${Math.round(dims.depth)} ft)` : ''),
    ],
    ['Zoning', parcel.zoning.join(' / ') || 'Not covered'],
    ['Current use', sentenceCase(parcel.currentUse)],
    ['Owner type', words(parcel.ownerType)],
    ['Assessed land', parcel.assessedLand === null ? '—' : formatDollars(parcel.assessedLand)],
  ]
  const lead = analysis?.options.find((o) => o.label === analysis.metrics?.option)
  // The land price is the "Land" row above, with its source.
  const editable =
    analysis?.assumptions.filter(
      (x) => x.editable && !(x.key === 'land_price' && analysis.metrics),
    ) ?? []
  return (
    <div className="report-cards">
      <section className="report-card">
        <h3>Parcel</h3>
        <dl className="fact-list">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
      {analysis && editable.length > 0 && (
        <section className="report-card">
          <h3>Pro forma assumptions</h3>
          <dl className="fact-list">
            {lead && (
              <div>
                <dt>
                  Sale basis<small>{lead.revenueBasis}</small>
                </dt>
                <dd />
              </div>
            )}
            {analysis.metrics && (
              <div>
                <dt>
                  Land<small>{analysis.metrics.landBasis.source}</small>
                </dt>
                <dd>{formatDollars(analysis.metrics.landBasis.value)}</dd>
              </div>
            )}
            {editable.map((x) => (
              <div key={x.key}>
                <dt>
                  {x.label}
                  <small>
                    {x.placeholder ? 'Placeholder, not a local benchmark' : x.source}
                    {x.min !== null && x.max !== null && x.min !== x.max
                      ? ` · range ${formatAssumptionRange(x.min, x.max, x.unit)}`
                      : ''}
                  </small>
                </dt>
                <dd>{formatAssumption(x.value, x.unit)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  )
}

/** Where the facts came from, and the versions that produced the report. */
export function AboutReport({
  analysis,
  freshness,
}: {
  analysis: Analysis
  freshness: Freshness | null
}) {
  const v = analysis.versions
  return (
    <footer className="report-foot">
      <p>
        A screening, not a zoning determination, legal advice or an engineering assessment;
        confirm with the Zoning Administrator before relying on it. Every finding shows its source
        and confidence; unknowns are never scored as clear. Costs marked placeholder are defaults,
        not local benchmarks.
      </p>
      {freshness &&
        (freshness.live.length > 0 ? (
          <p>
            <b>Live at {freshness.liveAt?.slice(0, 16).replace('T', ' ')} UTC:</b>{' '}
            {freshness.live.map(words).join(', ')}. Map layers and everything else come from the
            stored copy, refreshed on a schedule.
          </p>
        ) : (
          <p>
            <b>Stored copy only</b> (no live lookups for this report).
          </p>
        ))}
      {freshness && freshness.fellBack.length > 0 && (
        <p className="key-over">
          Live lookup failed, stored copy used: {freshness.fellBack.map(words).join(', ')}.
        </p>
      )}
      <p className="key-mono">
        Engine {v.engine} · {v.ruleset} · schema {v.schema}
        {freshness?.parcelsAsOf ? ` · parcels as of ${freshness.parcelsAsOf}` : ''}
        {v.dataAsOf ? ` · oldest data ${v.dataAsOf}` : ''}
      </p>
    </footer>
  )
}
