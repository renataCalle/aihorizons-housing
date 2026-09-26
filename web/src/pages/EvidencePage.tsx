import { useParams } from 'react-router'
import { fetchEvidence } from '../api'
import { useAsync } from '../lib/useAsync'

/** Placeholder until M4: the evidence drawer over the report. */
export function EvidencePage() {
  const { evidenceId = '' } = useParams()
  const evidence = useAsync(evidenceId, (signal) => fetchEvidence(evidenceId, signal))

  return (
    <aside className="report" aria-label="Evidence">
      {evidence.status === 'loading' && <p className="label">Loading evidence…</p>}
      {evidence.status === 'error' && (
        <p role="alert">Couldn't load this evidence: {evidence.error.message}</p>
      )}
      {evidence.status === 'ready' && (
        <>
          <p className="label">Evidence</p>
          <h2>{evidence.data.title}</h2>
          <p>{evidence.data.appliesTo}</p>
        </>
      )}
    </aside>
  )
}
