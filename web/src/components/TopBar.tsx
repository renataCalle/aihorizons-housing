import { BrandMark } from './BrandMark'

/** Glass top bar over the map: brand, search (M2), illustrative badge. */
export function TopBar({ illustrative }: { illustrative: boolean }) {
  return (
    <header className="map-topbar glass">
      <BrandMark />
      <div className="omnibox omnibox-placeholder">
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4-4" />
        </svg>
        <span>Search by parcel ID, address or description (coming in M2)</span>
      </div>
      <div className="map-topbar-end">
        {illustrative && <span className="badge-illustrative">Illustrative data</span>}
      </div>
    </header>
  )
}
