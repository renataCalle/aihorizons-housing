import { useEffect, useRef } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router'
import { fetchEvidence } from '../api'
import {
  formatMoneyRange,
  formatMonthYear,
  formatMonthsRange,
  formatPercentRange,
} from '../lib/format'
import { programLabel, reliefShortLabel } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { spanOf } from '../models/estimate'
import type { CodeSection, Evidence, EvidenceSource, Precedent } from '../models/evidence'
import type { NextStep, Program, Severity } from '../models/report'
import { checkDetail } from '../report/ruleChecks'

const SEVERITY_LABEL: Record<Severity, string> = {
  deal_risk: 'Deal risk',
  caution: 'Caution',
  minor: 'Minor',
  unknown: 'Unknown',
}

const OUTCOME_LABEL: Record<string, string> = {
  granted: 'Granted',
  denied: 'Denied',
  withdrawn: 'Withdrawn',
  pending: 'Pending',
  unknown: 'Unknown',
}

/**
 * /parcel/:id/evidence/:evidenceId: a drawer over the report (05-evidence.png). It shows
 * what the engine and the stored facts say about one finding or the approvals option, for
 * the same building the report scores (the report passes it as outlet context).
 */
export function EvidenceDrawer() {
  const { id = '', evidenceId = '' } = useParams()
  const program = useOutletContext<Program | null>()
  const navigate = useNavigate()
  const key = `${id}|${evidenceId}|${program?.productType}|${program?.units}`
  const evidence = useAsync(key, (signal) => fetchEvidence(id, evidenceId, signal, program))
  const close = `/parcel/${id}${window.location.search}`
  const drawerRef = useRef<HTMLElement>(null)

  useEffect(() => {
    drawerRef.current?.focus()
  }, [evidenceId])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && navigate(close)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, close])

  return (
    <>
      <Link className="drawer-scrim" to={close} aria-label="Close evidence" tabIndex={-1} />
      <aside className="evidence-drawer" aria-label="Evidence" ref={drawerRef} tabIndex={-1}>
        <Link className="icon-button evidence-close" to={close} aria-label="Close evidence">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </Link>
        {evidence.status === 'loading' && <p className="label">Loading evidence…</p>}
        {evidence.status === 'error' && (
          <p role="alert" className="evidence-error">
            Couldn't load this evidence: {evidence.error.message}
          </p>
        )}
        {evidence.status === 'ready' && <EvidenceBody evidence={evidence.data} />}
      </aside>
    </>
  )
}

function EvidenceBody({ evidence: e }: { evidence: Evidence }) {
  const approvals = e.kind === 'approvals'
  return (
    <>
      <div className="evidence-tags">
        <span className="kind-pill">{approvals ? 'Zoning relief' : e.category}</span>
        {e.illustrative && <span className="badge-illustrative">Illustrative data</span>}
      </div>
      <header className="evidence-head">
        <h2 className="evidence-title">
          {approvals && e.program
            ? `Approvals for ${programLabel(e.program.productType, e.program.units).toLowerCase()}`
            : e.title}
        </h2>
        {approvals && e.program ? (
          <p className="evidence-sub">
            Applies to: Best with approvals · {programLabel(e.program.productType, e.program.units)}
          </p>
        ) : (
          <p className="evidence-sub">
            {e.severity && (
              <span className={`severity-pill sev-${e.severity}`}>
                {SEVERITY_LABEL[e.severity]}
              </span>
            )}
            {e.confidence && <span>Confidence: {e.confidence}</span>}
          </p>
        )}
      </header>
      {approvals ? <ApprovalsBody evidence={e} /> : <FindingBody evidence={e} />}
      <p className="evidence-foot">
        Screening only. Zoning rules: {e.versions.ruleset}
        {e.versions.rulesetAsOf && `, code text as of ${e.versions.rulesetAsOf}`}
        {e.versions.dataAsOf && ` · oldest data ${e.versions.dataAsOf}`}.
      </p>
    </>
  )
}

function FindingBody({ evidence: e }: { evidence: Evidence }) {
  return (
    <>
      <section className="evidence-section">
        <h3 className="evidence-label">Impact</h3>
        <dl className="evidence-kv">
          <div>
            <dt>Added cost</dt>
            <dd>
              {e.cost
                ? `+${formatMoneyRange(e.cost)}`
                : e.severity === 'deal_risk'
                  ? 'Could end the deal'
                  : 'Not priced'}
            </dd>
          </div>
          <div>
            <dt>Added time</dt>
            <dd>{e.months ? `+${formatMonthsRange(e.months)}` : 'Not estimated'}</dd>
          </div>
        </dl>
      </section>
      <section className="evidence-section">
        <h3 className="evidence-label">Where this comes from</h3>
        {e.sources.length === 0 && <p className="evidence-muted">No source cited.</p>}
        {e.sources.map((s) => (
          <SourceRow key={`${s.source}|${s.codeSection}`} source={s} />
        ))}
      </section>
      <CodeSections sections={e.codeSections} />
      <Resolve text={e.howToResolve} step={e.resolvedBy} />
    </>
  )
}

function SourceRow({ source: s }: { source: EvidenceSource }) {
  return (
    <div className="evidence-source">
      <p>{s.source}</p>
      <p className="evidence-chips">
        <span className="code-chip">
          {s.codeSection ? `§ ${s.codeSection}` : 'No code section cited'}
        </span>
        {s.url && (
          <ExternalLink href={s.url}>{s.codeSection ? 'Open the source' : 'Open the data'}</ExternalLink>
        )}
      </p>
      <p className="evidence-muted">
        {s.asOf
          ? `Data as of ${formatMonthYear(s.asOf)}${s.asOfFromLayer ? ' (date of the data layer)' : ''}`
          : 'No as-of date recorded'}
      </p>
    </div>
  )
}

function ApprovalsBody({ evidence: e }: { evidence: Evidence }) {
  return (
    <>
      <section className="evidence-section">
        <h3 className="evidence-label">What the code requires</h3>
        {e.ruleChecks.length === 0 ? (
          <p className="evidence-muted">The engine lists no failing rule for this building.</p>
        ) : (
          <ul className="evidence-rules">
            {e.ruleChecks.map((c) => {
              const detail = checkDetail(c)
              return (
                <li key={c.id}>
                  <div>
                    <p>{c.label}</p>
                    {(c.note || detail) && (
                      <p className="evidence-muted">{[detail, c.note].filter(Boolean).join(' · ')}</p>
                    )}
                  </div>
                  <div className="evidence-rule-side">
                    <span className={`rule-chip ${c.status === 'rejected' ? 'risk' : 'caution'}`}>
                      {c.status === 'rejected' ? 'Not feasible' : reliefShortLabel(c.relief ?? '')}
                    </span>
                    {c.section && <span className="code-chip">§ {c.section}</span>}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>
      <CodeSections sections={e.codeSections} />
      <section className="evidence-section">
        <h3 className="evidence-label">Approval odds and time</h3>
        <dl className="evidence-kv">
          {e.approvalProbability && (
            <div>
              <dt>Approval odds</dt>
              <dd>{formatPercentRange(spanOf(e.approvalProbability))}</dd>
            </div>
          )}
          {e.approvalMonths && (
            <div>
              <dt>Approvals</dt>
              <dd>{formatMonthsRange(spanOf(e.approvalMonths))}</dd>
            </div>
          )}
          {e.monthsToPermitReady && (
            <div>
              <dt>Permit-ready</dt>
              <dd>{formatMonthsRange(spanOf(e.monthsToPermitReady))}</dd>
            </div>
          )}
        </dl>
        {e.entitlementBasis.length > 0 && (
          <p className="key-mono">Odds basis: {e.entitlementBasis.join('; ')}</p>
        )}
        {e.oddsNote && <p className="evidence-muted">{e.oddsNote}</p>}
      </section>
      {e.precedent && <PrecedentSection precedent={e.precedent} />}
      <Resolve text={e.howToResolve} step={e.resolvedBy} />
    </>
  )
}

/** "What the code says": each cited section's title and summary, with its dates. */
function CodeSections({ sections }: { sections: CodeSection[] }) {
  if (sections.length === 0) return null
  const links = [...new Set(sections.map((c) => c.url).filter((u): u is string => !!u))]
  return (
    <section className="evidence-section">
      <h3 className="evidence-label">What the code says</h3>
      <ul className="code-sections">
        {sections.map((c) => (
          <li key={c.section}>
            <p>
              <span className="code-chip">§ {c.section}</span> {c.title}
            </p>
            {c.summary && <p className="evidence-lead">{c.summary}</p>}
            <p className="evidence-muted">
              {[
                c.asOf && `Code text as of ${formatMonthYear(c.asOf)}`,
                c.effective && `last amended ${formatMonthYear(c.effective)}`,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </li>
        ))}
      </ul>
      <p className="evidence-muted">
        Summaries are drafted from the code text and not yet checked by a person. Read the
        section before relying on it.
      </p>
      {links.length > 0 && (
        <p className="evidence-chips">
          {links.map((url) => (
            <ExternalLink key={url} href={url}>
              Open the zoning code
            </ExternalLink>
          ))}
        </p>
      )}
    </section>
  )
}

function PrecedentSection({ precedent: p }: { precedent: Precedent }) {
  if (p.status === 'unavailable') {
    return (
      <section className="evidence-section">
        <h3 className="evidence-label">Similar cases nearby</h3>
        <div className="evidence-empty">
          <p>Zoning board decisions aren't available yet.</p>
          <p className="evidence-muted">
            So there are no nearby cases to compare with.{p.note && ` ${p.note}`}
          </p>
        </div>
      </section>
    )
  }
  return (
    <section className="evidence-section">
      <div className="evidence-label-row">
        <h3 className="evidence-label">Similar cases nearby</h3>
        {p.status === 'illustrative' && (
          <span className="badge-illustrative">Illustrative cases</span>
        )}
      </div>
      {p.granted !== null && p.total !== null && (
        <p className="precedent-count">
          <b>
            {p.granted} of {p.total}
          </b>{' '}
          granted
          {p.medianMonths !== null && ` · median ${p.medianMonths} months to decision`}
        </p>
      )}
      {p.cases.length > 0 && (
        <div className="case-table-wrap">
          <table className="case-table">
            <thead>
              <tr>
                <th scope="col">Case</th>
                <th scope="col">Area</th>
                <th scope="col">Request</th>
                <th scope="col">Outcome</th>
                <th scope="col" className="num">
                  Mo
                </th>
              </tr>
            </thead>
            <tbody>
              {p.cases.map((c) => (
                <tr key={c.id}>
                  <td className="mono">
                    {c.sourceUrl ? (
                      <a href={c.sourceUrl} target="_blank" rel="noopener noreferrer">
                        {c.id}
                      </a>
                    ) : (
                      c.id
                    )}
                  </td>
                  <td>{c.area ?? '—'}</td>
                  <td>{c.request ?? '—'}</td>
                  <td>
                    <span className={`outcome-pill outcome-${c.outcome}`}>
                      {OUTCOME_LABEL[c.outcome]}
                    </span>
                  </td>
                  <td className="num">{c.monthsToDecision ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {p.rule && <p className="evidence-muted">Similar means: {p.rule}.</p>}
      {p.aiExtracted && (
        <p className="evidence-muted">
          An AI model pulled these cases from zoning board decision PDFs. Each one links to its
          source decision.
        </p>
      )}
    </section>
  )
}

function Resolve({ text, step }: { text: string | null; step: NextStep | null }) {
  return (
    <section className="evidence-section">
      <h3 className="evidence-label">How to resolve</h3>
      {text ? (
        <p className="evidence-lead">{text}</p>
      ) : (
        <p className="evidence-muted">No resolution recorded.</p>
      )}
      {step && (
        <div className="resolve-step">
          <span className="step-n" aria-hidden="true">
            {step.order}
          </span>
          <div>
            <p className="finding-title">
              <span className="visually-hidden">Next step {step.order}: </span>
              {step.action}
            </p>
            <p className="finding-detail">{step.who}</p>
          </div>
          <b className="step-cost">{formatMoneyRange(step.cost)}</b>
        </div>
      )}
    </section>
  )
}

function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a className="external-link" href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 5h5v5M19 5l-8 8M18 14v5H5V6h5" />
      </svg>
      <span className="visually-hidden"> (opens in a new tab)</span>
    </a>
  )
}
