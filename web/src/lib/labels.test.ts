import { describe, expect, it } from 'vitest'
import {
  approvalLabel,
  feasibilityLabel,
  programLabel,
  rankedForLabel,
  reliefType,
  scoredLabel,
} from './labels'

describe('labels', () => {
  it('names programs', () => {
    expect(programLabel('townhome', 3)).toBe('3 townhomes')
    expect(programLabel('walkup', 6)).toBe('6-unit walk-up')
    expect(programLabel('triplex', 3)).toBe('Triplex')
    expect(programLabel('townhome', null)).toBe('Townhomes')
  })

  it('names approval paths from relief types', () => {
    expect(approvalLabel([])).toBe('By-right')
    expect(approvalLabel(['subdivision', 'variance'])).toBe('Subdivision + Variance')
    expect(approvalLabel(['subdivision'])).toBe('Subdivision')
    expect(approvalLabel(['administrator_exception', 'administrator_exception'])).toBe(
      'Administrator exception ×2',
    )
    expect(reliefType('special exception (911.04)')).toBe('special_exception')
  })

  it('names what a score is for', () => {
    expect(scoredLabel({ productType: 'townhome', units: 2, basis: 'up_to' })).toBe(
      'Up to 2 townhomes',
    )
    expect(scoredLabel({ productType: 'townhome', units: 3, basis: 'exact' })).toBe('3 townhomes')
    expect(scoredLabel({ productType: 'single_family', units: 1, basis: 'up_to' })).toBe(
      'Single-family home',
    )
    expect(scoredLabel({ productType: null, units: null, basis: 'pick' })).toBe('No building fits')
    expect(rankedForLabel('townhome', null)).toBe('townhomes')
    expect(rankedForLabel('townhome', 3)).toBe('3 townhomes')
    expect(feasibilityLabel('walkup')).toBe('Walk-up feasibility')
  })
})
