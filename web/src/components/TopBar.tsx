import { Omnibox } from '../search/Omnibox'
import { BrandMark } from './BrandMark'

/** Glass top bar over the map: brand, search box, illustrative badge. */
interface Props {
  illustrative: boolean
  query: string
  /** The query was read by the rule-based parser because AI search was unavailable. */
  basicSearch?: boolean
}

export function TopBar({ illustrative, query, basicSearch = false }: Props) {
  return (
    <header className="map-topbar glass">
      <BrandMark />
      <Omnibox key={query} variant="bar" initialText={query} />
      <div className="map-topbar-end">
        {basicSearch && (
          <span className="basic-search" title="AI search was unavailable; read with basic rules">
            Basic search
          </span>
        )}
        {illustrative && <span className="badge-illustrative">Illustrative data</span>}
      </div>
    </header>
  )
}
