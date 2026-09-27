/** A single rank tag's footprint on screen, in px, with a little room between tags. */
export const TAG_BOX = { width: 36, height: 30 }
/** Each extra number in a grouped pill widens it by about this much. */
export const TAG_STEP = 30

export interface TagPoint {
  id: string
  /** Screen position of the lot, in px; tags sit at the same offset from it */
  x: number
  y: number
}

export interface TagGroup {
  /** Lots in the group, best rank first; the pill sits at the first one's position */
  ids: string[]
  x: number
  y: number
}

function width(group: TagGroup, box: typeof TAG_BOX, step: number): number {
  return box.width + (group.ids.length - 1) * step
}

/** Do two pills overlap? Pills extend right from their position (anchored bottom-left). */
function overlap(a: TagGroup, b: TagGroup, box: typeof TAG_BOX, step: number): boolean {
  const [left, right] = a.x <= b.x ? [a, b] : [b, a]
  return right.x - left.x < width(left, box, step) && Math.abs(a.y - b.y) < box.height
}

/**
 * Every tag stays visible: tags that would overlap merge into one pill listing all their
 * numbers. A merged pill is wider, so merging repeats until no two pills overlap. `points` are
 * in rank order; each pill keeps its numbers in rank order and sits at its best lot.
 */
export function groupTags(points: TagPoint[], box = TAG_BOX, step = TAG_STEP): TagGroup[] {
  let groups: TagGroup[] = points.map((p) => ({ ids: [p.id], x: p.x, y: p.y }))
  const rank = new Map(points.map((p, i) => [p.id, i]))
  for (let merged = true; merged; ) {
    merged = false
    outer: for (let i = 0; i < groups.length; i++) {
      for (let j = i + 1; j < groups.length; j++) {
        if (!overlap(groups[i], groups[j], box, step)) continue
        // i comes first in rank order, so the merged pill sits at i's best lot.
        const ids = [...groups[i].ids, ...groups[j].ids].sort(
          (a, b) => (rank.get(a) ?? 0) - (rank.get(b) ?? 0),
        )
        groups = [...groups.slice(0, j), ...groups.slice(j + 1)]
        groups[i] = { ...groups[i], ids }
        merged = true
        break outer
      }
    }
  }
  return groups
}
