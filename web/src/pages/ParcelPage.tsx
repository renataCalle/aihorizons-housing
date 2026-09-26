import { Link, Outlet, useParams } from 'react-router'
import { fetchSiteReport } from '../api'
import { BrandMark } from '../components/BrandMark'
import { formatRange } from '../lib/format'
import { useAsync } from '../lib/useAsync'

/** Placeholder until M4: proves the API → adapter → view model path with Sample lot A. */
export function ParcelPage() {
  const { id = '' } = useParams()
  const report = useAsync(id, (signal) => fetchSiteReport(id, signal))

  return (
    <main className="page">
      <header className="topbar glass">
        <BrandMark />
      </header>
      <article className="report">
        {report.status === 'loading' && <p className="label">Loading report…</p>}
        {report.status === 'error' && (
          <p role="alert">Couldn't load this report: {report.error.message}</p>
        )}
        {report.status === 'ready' && (
          <>
            <p className="label">Site report</p>
            <h1 className="report-title">{report.data.parcel.name}</h1>
            <p className="mono report-id">
              {report.data.parcel.id} · {report.data.parcel.neighborhood} ·{' '}
              {report.data.parcel.zoningDistrict}
            </p>
            {report.data.illustrative && <span className="badge-illustrative">Illustrative data</span>}
            <div className="verdict">
              <p className="verdict-headline">{report.data.verdict.headline}</p>
              <p className="verdict-score">
                {report.data.verdict.score ?? '—'}
                {report.data.verdict.scoreRange && (
                  <span className="verdict-range">{formatRange(report.data.verdict.scoreRange)}</span>
                )}
              </p>
            </div>
            <p className="label">
              Rules {report.data.versions.ruleset} · Data as of {report.data.versions.dataAsOf}
            </p>
            {report.data.bestWithApprovals?.evidenceId && (
              <Link to={`evidence/${report.data.bestWithApprovals.evidenceId}`}>Evidence →</Link>
            )}
          </>
        )}
      </article>
      <Outlet />
    </main>
  )
}
