import { describe, expect, it } from 'vitest'
import { groupTags } from './rankTags'

const ids = (points: { id: string; x: number; y: number }[]) =>
  groupTags(points).map((g) => g.ids)

describe('groupTags', () => {
  it('keeps tags that are far apart on their own', () => {
    expect(
      ids([
        { id: 'a', x: 0, y: 0 },
        { id: 'b', x: 100, y: 0 },
        { id: 'c', x: 0, y: 100 },
      ]),
    ).toEqual([['a'], ['b'], ['c']])
  })

  it('merges overlapping tags into one pill at the best-ranked lot', () => {
    const [group] = groupTags([
      { id: 'first', x: 100, y: 100 },
      { id: 'second', x: 110, y: 105 },
    ])
    expect(group).toEqual({ ids: ['first', 'second'], x: 100, y: 100 })
  })

  it('keeps every tag: none is dropped', () => {
    const points = Array.from({ length: 9 }, (_, i) => ({ id: `r${i}`, x: i * 5, y: i * 3 }))
    expect(groupTags(points).flatMap((g) => g.ids).sort()).toEqual(points.map((p) => p.id).sort())
  })

  it('merges again when a wider pill reaches a neighbour, keeping rank order', () => {
    // a and b overlap; their pill is wider, so it now reaches c as well.
    expect(
      ids([
        { id: 'a', x: 0, y: 0 },
        { id: 'b', x: 20, y: 0 },
        { id: 'c', x: 50, y: 0 },
      ]),
    ).toEqual([['a', 'b', 'c']])
  })
})
