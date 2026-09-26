/** Blueprint crosshair on the selected parcel (MapBase.dc.html): dashed ring, faint ring, ticks. */
export function Crosshair() {
  return (
    <svg className="crosshair" width="104" height="104" viewBox="-52 -52 104 104" aria-hidden="true">
      <circle r="30" fill="none" stroke="var(--cobalt)" strokeWidth="1.2" strokeDasharray="3 4" />
      <circle r="44" fill="none" stroke="var(--cobalt)" strokeWidth="0.6" strokeOpacity="0.5" />
      <line x1="0" y1="-50" x2="0" y2="-32" stroke="var(--cobalt)" strokeWidth="1.2" />
      <line x1="0" y1="32" x2="0" y2="50" stroke="var(--cobalt)" strokeWidth="1.2" />
      <line x1="-50" y1="0" x2="-32" y2="0" stroke="var(--cobalt)" strokeWidth="1.2" />
      <line x1="32" y1="0" x2="50" y2="0" stroke="var(--cobalt)" strokeWidth="1.2" />
    </svg>
  )
}
