import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { detect, shouldLookUp } from './detect'

interface Case {
  text: string
  kind: string
  format?: string
  look_up?: boolean
}

const { cases } = JSON.parse(
  readFileSync(new URL('../../../fixtures/search/detect_cases.json', import.meta.url), 'utf8'),
) as { cases: Case[] }

describe('detect (shared cases with the API)', () => {
  it.each(cases)('$text → $kind', (c) => {
    expect(detect(c.text)).toEqual({ kind: c.kind, format: c.format ?? null })
  })
})

describe('shouldLookUp (shared cases with the API)', () => {
  it.each(cases.filter((c) => c.look_up !== undefined))('$text → $look_up', (c) => {
    expect(shouldLookUp(c.text, detect(c.text))).toBe(c.look_up)
  })
})
