import { describe, expect, it } from 'vitest'
import { approvalLabel, programLabel, reliefType } from './labels'

describe('labels', () => {
  it('names programs', () => {
    expect(programLabel('townhome', 3)).toBe('3 townhomes')
    expect(programLabel('walkup', 6)).toBe('6-unit walk-up')
    expect(programLabel('triplex', 3)).toBe('Triplex')
  })

  it('names approval paths from relief types', () => {
    expect(approvalLabel([])).toBe('By-right')
    expect(approvalLabel(['subdivision', 'variance'])).toBe('Subdivision + Variance')
    expect(approvalLabel(['subdivision'])).toBe('Subdivision')
    expect(reliefType('special exception (911.04)')).toBe('special_exception')
  })
})
