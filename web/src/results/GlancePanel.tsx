import type { ReactNode } from 'react'
import { BAND_LABEL, rankedForLabel } from '../lib/labels'
import type { Band } from '../models/report'
import type { AreaSummary } from '../models/search'

const BANDS: Band[] = ['fast_track', 'conditions', 'high_risk', 'unknown']

interface Props {
  /** The searched areas, or none for the whole map */
  areas: string[]
  summary: AreaSummary | null
  loading: boolean
  error: string | null
  onShowList: () => void
  layers: ReactNode
}

/**
 * The 3D view's left panel (ScoreView3D.dc.html): the searched lots at a glance. Every figure
 * comes from the API (POST /api/search/summary); the panel only lays them out.
 */
export function GlancePanel({ areas, summary: s, loading, error, onShowList, layers }: Props) {
  const place = areas.length === 1 ? areas[0] : areas.length ? 'These areas' : 'Your search'
  const most = Math.max(1, ...(s?.blockers.map((b) => b.lots * b.avgPoints) ?? []))
  return (
    <aside className="results-panel glass glance" aria-label={`${place} at a glance`}>
      <p className="label glance-kicker">
        {areas.length === 1 ? 'Neighborhood view' : 'Area view'}
        {s?.rankedFor && ` · ${rankedForLabel(s.rankedFor.type, s.rankedFor.units)}`}
      </p>
      <h2 className="glance-title">{place} at a glance</h2>

      {error && <p role="alert">Couldn't load the summary: {error}</p>}
      {!s && loading && <p className="label">Counting lots…</p>}

      {s && (
        <div className="glance-body">
          <section>
            <h3 className="glance-label">
              Lots <span className="glance-total">{s.lots}</span>
            </h3>
            <ul className="glance-bands">
              {BANDS.map((band) => (
                <li key={band}>
                  <span className={`swatch swatch-${band}`} aria-hidden="true" />
                  <span>{BAND_LABEL[band]}</span>
                  <b>{s.bands[band]}</b>
                </li>
              ))}
            </ul>
          </section>

          {s.blockers.length > 0 && (
            <section>
              <h3 className="glance-label">What holds sites back</h3>
              <ul className="glance-blockers">
                {s.blockers.map((b) => (
                  <li key={b.driver}>
                    <div className="glance-blocker-head">
                      <span>{b.label}</span>
                      <span className="glance-blocker-meta">
                        {b.lots} lots · −{b.avgPoints} pts avg
                      </span>
                    </div>
                    <span className="glance-bar" aria-hidden="true">
                      <span style={{ width: `${(100 * b.lots * b.avgPoints) / most}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
              <p className="glance-note">
                Points each constraint takes off the score of the lot's best-fit building, from
                the engine's score breakdown.
              </p>
            </section>
          )}

          <section className="glance-stats">
            <div>
              <b>{s.nearMisses}</b>
              <span>Near misses: lots that fail just one filter</span>
            </div>
            {s.assemblies > 0 && (
              <div>
                <b>{s.assemblies}</b>
                <span>Assemblies: small lots that work together</span>
              </div>
            )}
          </section>
        </div>
      )}

      <div className="results-foot">
        <button type="button" className="button-secondary" onClick={onShowList}>
          Show the ranked list
        </button>
        {layers}
      </div>
    </aside>
  )
}
