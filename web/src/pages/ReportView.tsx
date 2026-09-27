import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, Outlet, useNavigate, useParams, useSearchParams } from 'react-router'
import { fetchSiteReport } from '../api'
import { formatMoneyRange, formatNumberRange, formatSqft } from '../lib/format'
import { BAND_LABEL, programLabel } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { spanOf } from '../models/estimate'
import type { Analysis, Flag, Parcel, Program, Severity, SiteReport } from '../models/report'
import { BuildOptions } from '../report/BuildOptions'
import { KeyNumbers } from '../report/KeyNumbers'
import { AboutReport, ParcelFacts } from '../report/ParcelFacts'
import { RuleTable } from '../report/RuleTable'
import { useEvidenceLink } from '../report/evidenceLink'
import { formatCountyId } from '../search/highlight'
import { useMapScreen } from './mapScreenContext'

const SEVERITY_LABEL: Record<Severity, string> = {
  deal_risk: 'Deal risk',
  caution: 'Caution',
  minor: 'Minor',
  unknown: 'Unknown',
}

/** /parcel/:id: the site report as a panel over the map (docs/01, §4; 04-report-open.png). */
export function ReportView() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const s = useMapScreen()
  const [params] = useSearchParams()
  // The building the search asked for, unless the viewer switched to the engine's pick.
  const product = s.filters?.product
  const searched: Program | null = product?.type
    ? { productType: product.type, units: product.units }
    : null
  const showPick = params.get('pick') === 'engine'
  const program = showPick ? null : searched
  const [attempt, setAttempt] = useState(0)
  const report = useAsync(`${id}|${program?.productType}|${program?.units}#${attempt}`, (signal) =>
    fetchSiteReport(id, signal, program),
  )
  const panelRef = useRef<HTMLElement>(null)

  const back = `/search?${new URLSearchParams([
    ...new URLSearchParams(s.searchQuery),
    ['selected', id],
  ]).toString()}`
  const total = s.response?.total
  // Rank only means something when the report was opened from a search.
  const rank = s.searchQuery
    ? s.response?.results.find((r) => r.parcel.id === id)?.rank
    : undefined

  // Move focus into the panel when it opens, and back to the map with Escape.
  useEffect(() => {
    panelRef.current?.focus()
  }, [id])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('.evidence-drawer')) navigate(back)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, back])

  return (
    <>
      <Link className="back-pill glass" to={back}>
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M19 12H5M11 6l-6 6 6 6" />
        </svg>
        {total !== undefined && s.searchQuery ? `Back to ${total} lots` : 'Back to map'}
      </Link>

      <article
        ref={panelRef}
        className="report-panel"
        tabIndex={-1}
        aria-label="Site report"
        aria-busy={report.status === 'loading'}
      >
        <header className="report-head">
          <span className="label report-kicker">
            Site report{rank && total ? ` · ${String(rank).padStart(2, '0')} / ${total}` : ''}
          </span>
          <div className="report-actions">
            <button
              type="button"
              className="button-primary export-memo"
              disabled={report.status !== 'ready' || !report.data.analysis}
              onClick={() => report.status === 'ready' && printMemo(report.data)}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
              </svg>
              Export memo
            </button>
            <Link className="icon-button" to={back} aria-label="Close report">
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </Link>
          </div>
        </header>

        {report.status === 'loading' && <ReportLoading />}
        {report.status === 'error' && (
          <div className="report-none" role="alert">
            <p>Couldn't load this report: {report.error.message}</p>
            <button
              type="button"
              className="button-secondary"
              onClick={() => setAttempt((n) => n + 1)}
            >
              Try again
            </button>
          </div>
        )}
        {report.status === 'ready' && (
          <ReportBody
            report={report.data}
            programNote={
              searched && (
                <ProgramNote
                  searched={searched}
                  scored={report.data.program}
                  showPick={showPick}
                  pick={report.data.parcel}
                />
              )
            }
          />
        )}
      </article>

      <Outlet context={program} />
    </>
  )
}

/**
 * "Export memo": the browser's print dialog over the report's print stylesheet (report.css,
 * `@media print`), which also shows the sources appendix. The title names the saved PDF.
 */
function printMemo(report: SiteReport) {
  const title = document.title
  document.title = `Site memo - ${report.parcel.name}`
  window.print()
  document.title = title
}

function ReportLoading() {
  return (
    <ul className="report-checklist" aria-label="Loading the report">
      {['Zoning rules', 'Hazards and site costs', 'Market and land price', 'Next steps'].map(
        (step) => (
          <li key={step}>{step}…</li>
        ),
      )}
    </ul>
  )
}

/** Which building the report scores: the one searched for, or the engine's pick. */
function ProgramNote(props: {
  searched: Program
  scored: Program | null
  showPick: boolean
  /** The lot's summary: its engine pick and that pick's score */
  pick: Parcel
}) {
  const [params] = useSearchParams()
  const label = programLabel(props.searched.productType, props.searched.units).toLowerCase()
  const toggle = (pick: boolean) => {
    const next = new URLSearchParams(params)
    if (pick) next.set('pick', 'engine')
    else next.delete('pick')
    return `?${next}`
  }
  if (props.showPick) {
    return (
      <p className="program-note">
        Showing the engine’s best pick for this lot.{' '}
        <Link to={toggle(false)} replace>
          Score {label} instead
        </Link>
      </p>
    )
  }
  if (!props.scored) {
    return (
      <p className="program-note">
        This lot’s facts aren’t stored, so it can’t be scored for {label}: showing the engine’s
        pick.
      </p>
    )
  }
  const lead = props.pick.leadOption
  const better = lead && lead.productType !== props.scored.productType ? lead : null
  return (
    <p className="program-note">
      Scored for {label}, as searched.{' '}
      {better && (
        <>
          Better fit on this lot: {programLabel(better.productType, better.units)}
          {props.pick.score !== null && ` · ${props.pick.score}`}.{' '}
        </>
      )}
      <Link to={toggle(true)} replace>
        {better ? 'See it' : 'See the engine’s best pick'}
      </Link>
    </p>
  )
}

function ReportBody({ report, programNote }: { report: SiteReport; programNote: ReactNode }) {
  const { parcel, analysis } = report
  // Outside the city there is no neighbourhood: name the municipality instead.
  const place = parcel.neighborhood ?? parcel.municipality
  const title = place ? `${parcel.name}, ${place}` : parcel.name
  const meta = [
    formatCountyId(parcel.id),
    formatSqft(parcel.lotAreaSqft).replace('sq ft', 'SF'),
    ...parcel.zoning,
    parcel.currentUse,
  ]
  return (
    <>
      <h1 className="report-title">{title}</h1>
      <p className="report-meta">
        <span className="mono">{meta.join(' · ')}</span>
        {parcel.illustrative && <span className="badge-illustrative">Illustrative data</span>}
      </p>
      {analysis && programNote}
      {analysis ? (
        <AnalysisSections analysis={analysis} />
      ) : (
        <p className="report-none">
          {parcel.municipality && !parcel.neighborhood
            ? `Zoning not covered for ${parcel.municipality}.`
            : 'Not a development candidate, so it has no screening report.'}
        </p>
      )}
      <section className="report-section">
        <h2>{analysis ? 'Parcel and assumptions' : 'Parcel'}</h2>
        <ParcelFacts parcel={parcel} analysis={analysis} />
      </section>
      {analysis && <AboutReport analysis={analysis} freshness={report.freshness} />}
      {analysis && <SourcesAppendix analysis={analysis} />}
    </>
  )
}

function AnalysisSections({ analysis: a }: { analysis: Analysis }) {
  const band = a.verdict.band
  return (
    <>
      <section className="verdict-card" aria-label="Verdict">
        <div className="verdict-top">
          {/* The land risk ("High risk at the assessed value") outranks the band when set. */}
          <span className={`band-pill pill-${a.verdict.landRisk ? 'high_risk' : band}`}>
            {a.verdict.landRisk ?? BAND_LABEL[band]}
          </span>
          <div className="verdict-score-block">
            <span className="verdict-big">
              {a.verdict.score ?? '—'}
              {a.verdict.score !== null && <small>/100</small>}
            </span>
            {a.verdict.scoreRange && (
              <span className="label">
                Development ease · likely {formatNumberRange(spanOf(a.verdict.scoreRange))}
              </span>
            )}
          </div>
        </div>
        <p className="verdict-sentence">{a.verdict.headline}</p>
        {a.scoreComponents.length > 0 && (
          <div className="score-parts">
            <h2 className="label score-parts-title">Where the score comes from</h2>
            <ul>
              {a.scoreComponents.map((c) => (
                <li key={c.key}>
                  <span className="score-part-head">
                    <span>{c.label}</span>
                    <span className="mono">
                      {c.points}/{c.maxPoints}
                    </span>
                  </span>
                  <span className="score-bar" aria-hidden="true">
                    <span style={{ width: `${(100 * c.points) / Math.max(c.maxPoints, 1)}%` }} />
                  </span>
                  <span className="score-part-note">{c.note}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <KeyNumbers analysis={a} />

      <section className="report-section">
        <div className="report-section-head">
          <h2>What could kill this deal</h2>
          <span className="label">
            {a.flags.length} {a.flags.length === 1 ? 'finding' : 'findings'} · worst first
          </span>
        </div>
        <ul className="finding-list">
          {a.flags.map((f) => (
            <FlagRow key={f.id} flag={f} />
          ))}
        </ul>
        {a.cleared.length > 0 && (
          <p className="cleared">
            <span className="cleared-mark">
              <span aria-hidden="true">✓</span> Cleared
            </span>{' '}
            {a.cleared.join(' · ')}
          </p>
        )}
      </section>

      <BuildOptions analysis={a} />
      {a.ruleChecks && <RuleTable checks={a.ruleChecks} />}

      {a.nextSteps.length > 0 && <NextSteps analysis={a} />}
    </>
  )
}

function FlagRow({ flag: f }: { flag: Flag }) {
  const evidenceLink = useEvidenceLink()
  const ev = f.evidence[0]
  const section = f.evidence.find((e) => e.codeSection)?.codeSection
  const link = f.evidence.find((e) => e.url)?.url
  return (
    <li className="finding">
      <span className={`severity-pill sev-${f.severity}`}>{SEVERITY_LABEL[f.severity]}</span>
      <div className="finding-body">
        <p className="finding-title">{f.title}</p>
        <p className="finding-detail">{f.resolution}</p>
        <p className="finding-meta">
          {ev && (
            <span className="tag">
              {ev.source}
              {ev.asOf && ` · ${ev.asOf.slice(0, 4)}`}
            </span>
          )}
          {section && <span className="tag">§ {section}</span>}
          <span>Confidence: {f.confidence}</span>
        </p>
      </div>
      <div className="finding-side">
        {f.cost ? (
          <b>+{formatMoneyRange(f.cost)}</b>
        ) : (
          f.severity === 'deal_risk' && <b>Could end the deal</b>
        )}
        {f.months && (
          <span>
            +{f.months.low}–{f.months.high} months
          </span>
        )}
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer">
            See source<span aria-hidden="true"> →</span>
          </a>
        )}
        <Link className="evidence-link" to={evidenceLink(`flag.${f.id}`)}>
          Evidence<span className="visually-hidden"> for {f.title}</span>
          <span aria-hidden="true"> →</span>
        </Link>
      </div>
    </li>
  )
}

function NextSteps({ analysis: a }: { analysis: Analysis }) {
  const free = a.nextSteps.filter((s) => s.cost.high === 0).length
  return (
    <section className="report-section">
      <div className="report-section-head">
        <h2>What to check next</h2>
        {free > 0 && (
          <span className="free-chip">
            {free} free {free === 1 ? 'check' : 'checks'} first
          </span>
        )}
      </div>
      <ol className="step-list">
        {a.nextSteps.map((step) => (
          <li key={step.order}>
            <span className="step-n" aria-hidden="true">
              {step.order}
            </span>
            <div>
              <p className="finding-title">{step.action}</p>
              <p className="finding-detail">{step.why}</p>
            </div>
            <span className="step-who">{step.who}</span>
            <b className="step-cost">{formatMoneyRange(step.cost)}</b>
          </li>
        ))}
      </ol>
    </section>
  )
}

/** Printed memo only: every source the findings cite, once each. */
function SourcesAppendix({ analysis: a }: { analysis: Analysis }) {
  const seen = new Set<string>()
  const sources = a.flags
    .flatMap((f) => f.evidence)
    .filter((e) => {
      const key = `${e.source}|${e.codeSection}|${e.url}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  return (
    <section className="print-only sources-appendix">
      <h2>Sources</h2>
      <ol>
        {sources.map((e) => (
          <li key={`${e.source}|${e.codeSection}|${e.url}`}>
            {e.source}
            {e.codeSection && `, § ${e.codeSection}`}
            {e.asOf && `, as of ${e.asOf}`}
            {e.url && <span className="source-url">{e.url}</span>}
          </li>
        ))}
        <li>
          Zoning rules: {a.versions.ruleset}. Engine {a.versions.engine}, schema{' '}
          {a.versions.schema}
          {a.versions.dataAsOf && `, oldest data ${a.versions.dataAsOf}`}.
        </li>
      </ol>
    </section>
  )
}
