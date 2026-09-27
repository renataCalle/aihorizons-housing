import { describe, expect, it } from 'vitest'
import { visibleTags } from './rankTags'

describe('visibleTags', () => {
  it('keeps the better-ranked tag when two overlap', () => {
    const shown = visibleTags([
      { id: 'first', x: 100, y: 100 },
      { id: 'second', x: 110, y: 105 },
    ])
    expect([...shown]).toEqual(['first'])
  })

  it('shows tags that are far enough apart', () => {
    const shown = visibleTags([
      { id: 'a', x: 0, y: 0 },
      { id: 'b', x: 40, y: 0 },
      { id: 'c', x: 0, y: 40 },
    ])
    expect(shown.size).toBe(3)
  })

  it('compares each tag only with the tags shown', () => {
    // b clashes with a and is hidden; c clashes only with b, so it shows.
    const shown = visibleTags([
      { id: 'a', x: 0, y: 0 },
      { id: 'b', x: 30, y: 0 },
      { id: 'c', x: 60, y: 0 },
    ])
    expect([...shown]).toEqual(['a', 'c'])
  })
})
