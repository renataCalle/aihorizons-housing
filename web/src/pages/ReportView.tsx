import { useEffect, useRef } from 'react'
import { Link, Outlet, useNavigate, useParams } from 'react-router'
import { fetchSiteReport } from '../api'
import { formatMoneyRange, formatNumberRange, formatSqft } from '../lib/format'
import { BAND_LABEL } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { spanOf } from '../models/estimate'
import type { Analysis, Severity, SiteReport } from '../models/report'
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
  const report = useAsync(id, (signal) => fetchSiteReport(id, signal))
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
        {total !== undefined && s.searchQuery ? `Back to ${total} sites` : 'Back to map'}
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
          <Link className="icon-button" to={back} aria-label="Close report">
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </Link>
        </header>

        {report.status === 'loading' && <ReportLoading />}
        {report.status === 'error' && (
          <p role="alert">Couldn't load this report: {report.error.message}</p>
        )}
        {report.status === 'ready' && <ReportBody report={report.data} />}
      </article>

      <Outlet />
    </>
  )
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

function ReportBody({ report }: { report: SiteReport }) {
  const { parcel, analysis } = report
  const title = parcel.neighborhood ? `${parcel.name}, ${parcel.neighborhood}` : parcel.name
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
      {analysis ? (
        <AnalysisSections analysis={analysis} />
      ) : (
        <p className="report-none">
          {parcel.municipality && !parcel.neighborhood
            ? `Zoning not covered for ${parcel.municipality}.`
            : 'Not a development candidate, so it has no screening report.'}
        </p>
      )}
    </>
  )
}

function AnalysisSections({ analysis: a }: { analysis: Analysis }) {
  const band = a.verdict.band
  return (
    <>
      <section className="verdict-card" aria-label="Verdict">
        <div className="verdict-top">
          <span className={`band-pill pill-${band}`}>{BAND_LABEL[band]}</span>
          <div className="verdict-score-block">
            <span className="verdict-big">
              {a.verdict.score ?? '—'}
              {a.verdict.score !== null && <small>/100</small>}
            </span>
            {a.verdict.scoreRange && (
              <span className="label">
                Development ease · range {formatNumberRange(spanOf(a.verdict.scoreRange))}
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

      <section className="report-section">
        <div className="report-section-head">
          <h2>What could kill this deal</h2>
          <span className="label">
            {a.flags.length} {a.flags.length === 1 ? 'finding' : 'findings'} · worst first
          </span>
        </div>
        <ul className="finding-list">
          {a.flags.map((f) => (
            <li key={f.id} className="finding">
              <span className={`severity-pill sev-${f.severity}`}>{SEVERITY_LABEL[f.severity]}</span>
              <div>
                <p className="finding-title">{f.title}</p>
                <p className="finding-detail">{f.resolution}</p>
                <p className="finding-meta">
                  {f.cost && `Cost ${formatMoneyRange(f.cost)} · `}
                  Confidence {f.confidence}
                  {f.evidence[0] && ` · ${f.evidence[0].source}`}
                </p>
              </div>
            </li>
          ))}
        </ul>
        {a.cleared.length > 0 && (
          <p className="cleared">
            <span className="label">Cleared</span> {a.cleared.join(' · ')}
          </p>
        )}
      </section>

      {a.nextSteps.length > 0 && (
        <section className="report-section">
          <h2>What to check next</h2>
          <ol className="step-list">
            {a.nextSteps.map((step) => (
              <li key={step.order}>
                <p className="finding-title">{step.action}</p>
                <p className="finding-detail">{step.why}</p>
                <p className="finding-meta">
                  {step.who} · {formatMoneyRange(step.cost)}
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="report-foot">
        Screening estimate, not a zoning determination. Rules {a.versions.ruleset} · engine{' '}
        {a.versions.engine} · data as of {a.versions.dataAsOf ?? 'unknown'}.
      </footer>
    </>
  )
}
