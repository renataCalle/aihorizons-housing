import { Link, Outlet, useParams } from 'react-router'
import { fetchSiteReport } from '../api'
import { BrandMark } from '../components/BrandMark'
import { formatNumberRange } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { spanOf } from '../models/estimate'

/** Placeholder until M4: proves the API → adapter → view model path. */
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
              {report.data.parcel.id}
              {report.data.parcel.neighborhood && ` · ${report.data.parcel.neighborhood}`}
              {report.data.parcel.zoning.length > 0 && ` · ${report.data.parcel.zoning.join(', ')}`}
            </p>
            {report.data.parcel.illustrative && (
              <span className="badge-illustrative">Illustrative data</span>
            )}
            {report.data.analysis ? (
              <>
                <div className="verdict">
                  <p className="verdict-headline">{report.data.analysis.verdict.headline}</p>
                  <p className="verdict-score">
                    {report.data.analysis.verdict.score ?? '—'}
                    {report.data.analysis.verdict.scoreRange && (
                      <span className="verdict-range">
                        {formatNumberRange(spanOf(report.data.analysis.verdict.scoreRange))}
                      </span>
                    )}
                  </p>
                </div>
                <p className="label">
                  Rules {report.data.analysis.versions.ruleset} · Data as of{' '}
                  {report.data.analysis.versions.dataAsOf ?? 'unknown'}
                </p>
              </>
            ) : (
              <p>Not a development candidate.</p>
            )}
            <Link to="evidence/ev-variance-4-townhomes">Evidence →</Link>
          </>
        )}
      </article>
      <Outlet />
    </main>
  )
}
