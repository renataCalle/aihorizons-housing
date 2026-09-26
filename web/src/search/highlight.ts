/** Dashed display form of a compact county ID: 0055A00137000000 → 0055-A-00137-0000-00. */
export function formatCountyId(compact: string): string {
  const m = /^(\d{4})([A-Z])(\d{5})(\d{4})(\d{2})$/.exec(compact)
  return m ? m.slice(1).join('-') : compact
}

/**
 * Split `display` into the part that matches what the user typed and the rest, ignoring
 * dashes, spaces and case: typing "0000x00" highlights "0000-X-00" in "0000-X-00000-0000-00".
 */
export function splitMatch(display: string, typed: string): [string, string] {
  const wanted = typed.replace(/[\s-]/g, '').toUpperCase()
  if (!wanted) return ['', display]
  let seen = 0
  for (let i = 0; i < display.length; i++) {
    const ch = display[i]
    if (ch === '-' || ch === ' ') continue
    if (ch.toUpperCase() !== wanted[seen]) return ['', display]
    seen++
    if (seen === wanted.length) return [display.slice(0, i + 1), display.slice(i + 1)]
  }
  return ['', display]
}
