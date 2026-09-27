import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { fetchEvidence } from '../api'
import { useAsync } from '../lib/useAsync'

/** /parcel/:id/evidence/:evidenceId: a drawer over the report (05-evidence.png). Full in M4. */
export function EvidenceDrawer() {
  const { id = '', evidenceId = '' } = useParams()
  const navigate = useNavigate()
  const evidence = useAsync(evidenceId, (signal) => fetchEvidence(evidenceId, signal))
  const close = `/parcel/${id}${window.location.search}`

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && navigate(close)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, close])

  return (
    <>
      <Link className="drawer-scrim" to={close} aria-label="Close evidence" tabIndex={-1} />
      <aside className="evidence-drawer" aria-label="Evidence">
        <Link className="icon-button evidence-close" to={close} aria-label="Close evidence">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </Link>
        {evidence.status === 'loading' && <p className="label">Loading evidence…</p>}
        {evidence.status === 'error' && (
          <p role="alert">Couldn't load this evidence: {evidence.error.message}</p>
        )}
        {evidence.status === 'ready' && (
          <>
            <h2 className="report-title">{evidence.data.title}</h2>
            <p>{evidence.data.appliesTo}</p>
          </>
        )}
      </aside>
    </>
  )
}
