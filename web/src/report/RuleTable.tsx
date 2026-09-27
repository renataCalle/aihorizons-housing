import { formatPercent } from '../lib/format'
import { programLabel, reliefShortLabel } from '../lib/labels'
import type { ProgramEvaluation, RuleCheck, RuleChecks } from '../models/report'
import { checkDetail, ruleTable } from './ruleChecks'

const OUTCOME: Record<ProgramEvaluation['outcome'], [string, string]> = {
  by_right: ['Allowed outright', 'ok'],
  needs_approval: ['Needs approval', 'caution'],
  rejected: ['Not feasible', 'risk'],
}

const SITE_STATUS: Record<RuleChecks['siteChecks'][number]['status'], [string, string]> = {
  applies: ['Applies', 'caution'],
  clear: ['Clear', 'ok'],
  unknown: ['Unknown', 'unknown'],
}

function Cell({ check }: { check: RuleCheck | null }) {
  if (!check || check.status === 'not_applicable') {
    return (
      <td className="rule-na">
        <span aria-hidden="true">—</span>
        <span className="visually-hidden">Does not apply</span>
      </td>
    )
  }
  const detail = checkDetail(check)
  return (
    <td>
      {check.status === 'pass' && (
        <span className="rule-pass">
          <span aria-hidden="true">✓</span> Passes
        </span>
      )}
      {check.status === 'needs_approval' && (
        <span className="rule-chip caution">{reliefShortLabel(check.relief ?? '')}</span>
      )}
      {check.status === 'rejected' && (
        <span className="rule-chip risk">
          <span aria-hidden="true">✗ </span>Not feasible
        </span>
      )}
      {detail && <span className="rule-sub">{detail}</span>}
    </td>
  )
}

/** "Rule by rule": every zoning rule against each building type, then site-wide rules. */
export function RuleTable({ checks: rc }: { checks: RuleChecks }) {
  const { columns, rows } = ruleTable(rc.programs)
  return (
    <section className="report-section">
      <div className="report-section-head">
        <h2>Rule by rule</h2>
        <span className="label">
          {rc.district} · {rc.scenario} setbacks · {rc.programs.length} buildings tested
        </span>
      </div>
      <div className="rule-table-wrap" tabIndex={0} aria-label="Zoning rules by building type">
        <table className="rule-table">
          <thead>
            <tr>
              <th scope="col">Zoning rule</th>
              {columns.map((p) => (
                <th
                  key={`${p.productType}-${p.units}`}
                  scope="col"
                  className={p.chosenAs ? 'is-picked' : undefined}
                >
                  {programLabel(p.productType, p.units)}
                  {p.chosenAs && (
                    <span className="lead-badge">
                      {p.chosenAs === 'by_right' ? 'By-right option' : 'With-approvals option'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">
                  {row.label}
                  {row.sections.length > 0 && (
                    <span className="rule-sub">§ {row.sections.join(' / ')}</span>
                  )}
                </th>
                {row.cells.map((c, i) => (
                  <Cell key={i} check={c} />
                ))}
              </tr>
            ))}
            <tr className="rule-foot">
              <th scope="row">Approval odds</th>
              {columns.map((p, i) => (
                <td key={i}>
                  {p.approvalProbability ? (
                    <>
                      <b>{formatPercent(p.approvalProbability.p50)}</b>
                      {p.outcome !== 'by_right' && (
                        <span className="rule-sub">
                          {formatPercent(p.approvalProbability.p10)}–
                          {formatPercent(p.approvalProbability.p90)}
                        </span>
                      )}
                    </>
                  ) : (
                    '—'
                  )}
                </td>
              ))}
            </tr>
            <tr className="rule-foot">
              <th scope="row">Result</th>
              {columns.map((p, i) => (
                <td key={i}>
                  <span className={`rule-chip ${OUTCOME[p.outcome][1]}`}>
                    {OUTCOME[p.outcome][0]}
                  </span>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="report-note">{rc.oddsNote}</p>
      {rc.uncoveredDistricts.length > 0 && (
        <p className="report-note">
          Not covered yet: {rc.uncoveredDistricts.join(', ')} (this part of the lot is not
          evaluated).
        </p>
      )}
      <div className="report-cards">
        <section className="report-card">
          <h3>Rules for the whole site</h3>
          <ul className="plain-list">
            {rc.siteChecks.map((c) => (
              <li key={c.id}>
                <span className={`rule-chip ${SITE_STATUS[c.status][1]}`}>
                  {SITE_STATUS[c.status][0]}
                </span>{' '}
                <b>{c.label}</b>
                <span className="rule-sub">
                  § {c.section}
                  {c.note && ` · ${c.note}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
        {rc.notChecked.length > 0 && (
          <section className="report-card">
            <h3>Not checked yet</h3>
            <ul className="plain-list">
              {rc.notChecked.map((n) => (
                <li key={`${n.section}-${n.label}`}>
                  <b>{n.label}</b>
                  <span className="rule-sub">
                    § {n.section} · {n.reason}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </section>
  )
}
