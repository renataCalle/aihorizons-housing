import { useId, useState } from 'react'
import { fetchNeighborhoods } from '../api'
import { useAsync } from '../lib/useAsync'
import type {
  ApprovalPath,
  Constraint,
  Filters,
  OwnerType,
  ProductType,
} from '../models/filters'

const PRODUCTS: [ProductType | '', string][] = [
  ['', 'Any building'],
  ['single_family', 'Single-family home'],
  ['duplex', 'Duplex'],
  ['triplex', 'Triplex'],
  ['townhome', 'Townhomes'],
  ['walkup', 'Walk-up'],
]

const APPROVALS: [string, string, ApprovalPath[]][] = [
  ['any', 'Any approval path', []],
  ['by_right', 'By-right only', ['by_right']],
  ['no_hearing', 'No zoning board hearing', ['by_right', 'administrative']],
  ['variances', 'Variances OK', ['by_right', 'administrative', 'special_exception', 'variance']],
]

const CONSTRAINTS: [Constraint, string][] = [
  ['undermined', 'Undermined'],
  ['flood_zone', 'Flood zone'],
  ['landslide', 'Landslide-prone'],
  ['steep_slope', 'Steep slope'],
  ['combined_sewer', 'Combined sewer'],
]

const PUBLIC: OwnerType[] = ['land_bank', 'ura', 'city']

function numberOrNull(value: string): number | null {
  const n = Number(value)
  return value.trim() === '' || Number.isNaN(n) ? null : n
}

/** The full filter controls (docs/01, §3 "Edit filters"). Every change applies right away. */
export function FilterEditor({
  filters,
  onChange,
}: {
  filters: Filters
  onChange: (next: Filters) => void
}) {
  const id = useId()
  const [allAreas, setAllAreas] = useState(false)
  const neighborhoods = useAsync('neighborhoods', fetchNeighborhoods)
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })

  const approval =
    APPROVALS.find(([, , paths]) => JSON.stringify(paths) === JSON.stringify(filters.approvalPaths))?.[0] ??
    'custom'
  const listed =
    neighborhoods.status === 'ready'
      ? neighborhoods.data.filter(
          (n) => allAreas || n.candidates > 0 || filters.areas.includes(n.name),
        )
      : []
  const nearTransit = filters.near.some((n) => n.feature === 'transit_stop')
  const publicOnly = PUBLIC.every((o) => filters.ownerTypes.includes(o))

  return (
    <form className="filter-editor" onSubmit={(e) => e.preventDefault()}>
      <fieldset>
        <legend>What to build</legend>
        <div className="field-row">
          <label className="field">
            <span>Building</span>
            <select
              value={filters.product?.type ?? ''}
              onChange={(e) => {
                const type = (e.target.value || null) as ProductType | null
                const units = filters.product?.units ?? null
                set({ product: type || units ? { type, units } : null })
              }}
            >
              {PRODUCTS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field field-narrow">
            <span>Units (at least)</span>
            <input
              type="number"
              min={1}
              max={24}
              inputMode="numeric"
              value={filters.product?.units ?? ''}
              onChange={(e) => {
                const units = numberOrNull(e.target.value)
                const type = filters.product?.type ?? null
                set({ product: type || units ? { type, units } : null })
              }}
            />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Approval path</legend>
        {APPROVALS.map(([value, label, paths]) => (
          <label key={value} className="check">
            <input
              type="radio"
              name={`${id}-approval`}
              checked={approval === value}
              onChange={() => set({ approvalPaths: paths })}
            />
            {label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Areas</legend>
        {neighborhoods.status === 'loading' && <p className="field-note">Loading neighborhoods…</p>}
        <div className="area-list">
          {listed.map((n) => (
            <label key={n.name} className="check">
              <input
                type="checkbox"
                checked={filters.areas.includes(n.name)}
                onChange={(e) =>
                  set({
                    areas: e.target.checked
                      ? [...filters.areas, n.name]
                      : filters.areas.filter((a) => a !== n.name),
                  })
                }
              />
              {n.name}
              {n.candidates > 0 && <span className="field-count">{n.candidates}</span>}
            </label>
          ))}
        </div>
        <button type="button" className="link-button" onClick={() => setAllAreas((v) => !v)}>
          {allAreas ? 'Only areas with sites' : 'Show all 90 neighborhoods'}
        </button>
      </fieldset>

      <fieldset>
        <legend>Land and lot</legend>
        <div className="field-row">
          <label className="field">
            <span>Max land price ($)</span>
            <input
              type="number"
              min={0}
              step={1000}
              inputMode="numeric"
              value={filters.maxLandPrice ?? ''}
              onChange={(e) => set({ maxLandPrice: numberOrNull(e.target.value) })}
            />
          </label>
        </div>
        <div className="field-row">
          <label className="field">
            <span>Lot min (sq ft)</span>
            <input
              type="number"
              min={0}
              step={100}
              value={filters.lotMinSqft ?? ''}
              onChange={(e) => set({ lotMinSqft: numberOrNull(e.target.value) })}
            />
          </label>
          <label className="field">
            <span>Lot max (sq ft)</span>
            <input
              type="number"
              min={0}
              step={100}
              value={filters.lotMaxSqft ?? ''}
              onChange={(e) => set({ lotMaxSqft: numberOrNull(e.target.value) })}
            />
          </label>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.maxSteepSlopePct !== null && filters.maxSteepSlopePct <= 5}
            onChange={(e) => set({ maxSteepSlopePct: e.target.checked ? 5 : null })}
          />
          Flat lots (under 5% steep slope)
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={nearTransit}
            onChange={(e) =>
              set({
                near: e.target.checked
                  ? [...filters.near, { feature: 'transit_stop', withinFt: 1320 }]
                  : filters.near.filter((n) => n.feature !== 'transit_stop'),
              })
            }
          />
          Within ¼ mi of transit
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.vacantOnly}
            onChange={(e) => set({ vacantOnly: e.target.checked })}
          />
          Vacant only
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={publicOnly}
            onChange={(e) => set({ ownerTypes: e.target.checked ? PUBLIC : [] })}
          />
          Public land (land bank, URA, city)
        </label>
      </fieldset>

      <fieldset>
        <legend>Exclude</legend>
        {CONSTRAINTS.map(([value, label]) => (
          <label key={value} className="check">
            <input
              type="checkbox"
              checked={filters.excludeConstraints.includes(value)}
              onChange={(e) =>
                set({
                  excludeConstraints: e.target.checked
                    ? [...filters.excludeConstraints, value]
                    : filters.excludeConstraints.filter((c) => c !== value),
                })
              }
            />
            {label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Show</legend>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.includeUnknowns}
            onChange={(e) => set({ includeUnknowns: e.target.checked })}
          />
          Sites with unknown data
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.showAssemblies}
            onChange={(e) => set({ showAssemblies: e.target.checked })}
          />
          Lots that work together
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={filters.showNearMisses}
            onChange={(e) => set({ showNearMisses: e.target.checked })}
          />
          Near misses (one filter away)
        </label>
      </fieldset>
    </form>
  )
}
