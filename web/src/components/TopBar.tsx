import { Omnibox } from '../search/Omnibox'
import { BrandMark } from './BrandMark'

/** Glass top bar over the map: brand, search box, illustrative badge. */
interface Props {
  illustrative: boolean
  query: string
}

export function TopBar({ illustrative, query }: Props) {
  return (
    <header className="map-topbar glass">
      <BrandMark />
      <Omnibox key={query} variant="bar" initialText={query} />
      <div className="map-topbar-end">
        {illustrative && <span className="badge-illustrative">Illustrative data</span>}
      </div>
    </header>
  )
}
