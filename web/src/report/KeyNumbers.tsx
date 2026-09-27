import {
  formatDollars,
  formatMaxLand,
  formatMoneyRange,
  formatMonthsRange,
  formatPercent,
} from '../lib/format'
import { approvalLabel, programLabel, reliefType } from '../lib/labels'
import { spanOf } from '../models/estimate'
import type { Analysis } from '../models/report'

/** Three cards under the verdict: approval path, site cost premium, max land price. */
export function KeyNumbers({ analysis: a }: { analysis: Analysis }) {
  const m = a.metrics
  const lead = m && a.options.find((o) => o.label === m.option)
  if (!m || !lead) return null
  const margin = a.assumptions.find((x) => x.key === 'target_margin')
  const premium = m.siteCostPremium
  const asking = m.landBasis.source === 'user input'
  return (
    <div className="key-numbers">
      <section className="key-card">
        <h2 className="label">Approval path</h2>
        <p className="key-value">{approvalLabel(lead.relief.map(reliefType))}</p>
        <p className="key-note">
          {programLabel(lead.productType, lead.units)} ·{' '}
          {formatMonthsRange(spanOf(lead.monthsToPermitReady))} to permit-ready
        </p>
        <p className="key-mono">{a.versions.ruleset}</p>
      </section>
      <section className="key-card">
        <h2 className="label">Site cost premium</h2>
        <p className="key-value">
          {premium.high > 0 ? `+${formatMoneyRange(premium)}` : 'None priced'}
        </p>
        {premium.drivers.length > 0 && (
          <p className="key-note">{premium.drivers.slice(0, 3).join(', ')}</p>
        )}
      </section>
      <section className="key-card">
        <h2 className="label">
          Max land price{margin ? ` at ${formatPercent(margin.value)} margin` : ''}
        </h2>
        <p className="key-value">{formatMaxLand(spanOf(m.maxLandPrice))}</p>
        {m.landOverMax && (
          <p className="key-note key-over">
            <span aria-hidden="true">↓ </span>
            {asking ? 'Asking' : 'Assessed land'} {formatDollars(m.landBasis.value)} is{' '}
             {formatMoneyRange(m.landOverMax)} over
          </p>
        )}
        <p className="key-mono">
          {m.comps.count} sales within {m.comps.radiusMi} mi · {m.comps.windowMonths} mo
        </p>
      </section>
    </div>
  )
}
