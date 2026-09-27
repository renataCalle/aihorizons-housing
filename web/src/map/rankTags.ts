/** A rank tag's footprint on screen, in px, with a little room between tags. */
export const TAG_BOX = { width: 36, height: 30 }

export interface TagPoint {
  id: string
  /** Screen position of the lot, in px; tags sit at the same offset from it */
  x: number
  y: number
}

/**
 * Which tags to show: best rank first (`points` in rank order), skipping any tag that would
 * overlap one already shown. The hidden ones appear as the map zooms in and they spread out.
 */
export function visibleTags(points: TagPoint[], box = TAG_BOX): Set<string> {
  const shown: TagPoint[] = []
  for (const p of points) {
    const clash = shown.some(
      (q) => Math.abs(p.x - q.x) < box.width && Math.abs(p.y - q.y) < box.height,
    )
    if (!clash) shown.push(p)
  }
  return new Set(shown.map((p) => p.id))
}
