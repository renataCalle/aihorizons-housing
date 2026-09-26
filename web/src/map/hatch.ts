/** A 6px diagonal hatch for unknown parcels: `unknown` lines on `unknownTint` (RGBA pixels). */
export function hatchPattern(line: string, background: string, size = 6) {
  const [lr, lg, lb] = hexToRgb(line)
  const [br, bg, bb] = hexToRgb(background)
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const onLine = (x + y) % size === 0 || (x + y) % size === size - 1
      const i = (y * size + x) * 4
      data.set(onLine ? [lr, lg, lb, 255] : [br, bg, bb, 255], i)
    }
  }
  return { width: size, height: size, data }
}

export function hexToRgb(hex: string): [number, number, number] {
  const value = hex.trim().replace('#', '')
  const full = value.length === 3 ? [...value].map((c) => c + c).join('') : value
  const n = Number.parseInt(full, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
