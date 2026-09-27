import { useLocation, useParams } from 'react-router'

/**
 * The drawer route for one finding (`flag.<id>`) or the approvals option
 * (`option.with_relief`). Keeps the query string so closing returns to the same report.
 */
export function useEvidenceLink(): (evidenceId: string) => string {
  const { id = '' } = useParams()
  const { search } = useLocation()
  return (evidenceId) => `/parcel/${id}/evidence/${encodeURIComponent(evidenceId)}${search}`
}
