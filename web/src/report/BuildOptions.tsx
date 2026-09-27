import { formatDollars, formatMonthsRange, formatPercentRange } from '../lib/format'
import { approvalLabel, programLabel, reliefType } from '../lib/labels'
import { spanOf } from '../models/estimate'
import type { Analysis } from '../models/report'

/** "What you can build": the best by-right and best with-approvals programs. */
export function BuildOptions({ analysis: a }: { analysis: Analysis }) {
  const lead = a.metrics?.option
  const scenario = a.setbackScenario
  return (
    <section className="report-section">
      <div className="report-section-head">
        <h2>What you can build</h2>
        {scenario && <span className="label">{scenario} setbacks</span>}
      </div>
      {a.options.length === 0 ? (
        <p className="report-none">No building type the engine tested works on this lot.</p>
      ) : (
        <div className="option-grid">
          {a.options.map((o) => {
            const relief = o.relief.map(reliefType)
            return (
              <section
                key={o.label}
                className={o.label === lead ? 'option-card is-lead' : 'option-card'}
              >
                <div className="option-top">
                  <span className="label">
                    {o.label === 'by_right' ? 'Best by-right' : 'Best with approvals'}
                  </span>
                  {o.label === lead && <span className="lead-badge">Leading option</span>}
                </div>
                <h3 className="option-name">{programLabel(o.productType, o.units)}</h3>
                <p className="option-size">
                  {o.units} {o.units === 1 ? 'home' : 'homes'} · about{' '}
                  {o.unitSqft.toLocaleString('en-US')} sq ft each
                </p>
                <dl className="option-kv">
                  <div>
                    <dt>Margin</dt>
                    <dd>{formatPercentRange(spanOf(o.margin))}</dd>
                  </div>
                  <div>
                    <dt>Permit-ready</dt>
                    <dd>{formatMonthsRange(spanOf(o.monthsToPermitReady))}</dd>
                  </div>
                  <div>
                    <dt>Approvals</dt>
                    <dd>{relief.length ? approvalLabel(relief) : 'None'}</dd>
                  </div>
                </dl>
                <p className="key-mono">
                  {o.entitlementBasis.length
                    ? o.entitlementBasis.join('; ')
                    : `By right under ${a.versions.ruleset}`}
                </p>
              </section>
            )
          })}
        </div>
      )}
      {a.metrics && (
        <p className="report-note">
          Margins assume {formatDollars(a.metrics.landBasis.value)} for land (
          {a.metrics.landBasis.source}), default costs and {a.metrics.comps.count} nearby sales.
        </p>
      )}
    </section>
  )
}
