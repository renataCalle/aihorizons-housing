import { describe, expect, it } from 'vitest'
import type { ProgramEvaluation, RuleCheck } from '../models/report'
import { checkDetail, ruleTable } from './ruleChecks'

function check(over: Partial<RuleCheck>): RuleCheck {
  return {
    id: 'min_lot_size',
    label: 'Lot meets the minimum lot size',
    section: '925.01.C.2',
    status: 'pass',
    required: null,
    provided: null,
    unit: null,
    relief: null,
    note: null,
    ...over,
  }
}

function program(over: Partial<ProgramEvaluation>, checks: RuleCheck[]): ProgramEvaluation {
  return {
    productType: 'duplex',
    units: 2,
    outcome: 'rejected',
    checks,
    approvalProbability: null,
    representative: true,
    chosenAs: null,
    ...over,
  }
}

describe('rule checks', () => {
  it('says how far a failing lot falls short', () => {
    const c = check({ status: 'needs_approval', required: 3200, provided: 2321, unit: 'sf' })
    expect(checkDetail(c)).toBe('27% short')
  })

  it('shows the measurement for a pass', () => {
    const c = check({ id: 'fits_envelope', required: 1500, provided: 2321, unit: 'sf' })
    expect(checkDetail(c)).toBe('needs 1,500 sq ft · room for 2,321')
  })

  it('names a use the district does not allow', () => {
    expect(checkDetail(check({ status: 'rejected', relief: 'use_variance' }))).toBe(
      'use not allowed',
    )
  })

  it('keeps representative and chosen columns and drops rules that apply to none', () => {
    const na = check({ id: 'subdivision', status: 'not_applicable' })
    const { columns, rows } = ruleTable([
      program({ chosenAs: 'with_relief', representative: false }, [check({}), na]),
      program({ representative: false }, [check({}), na]),
      program({}, [check({ section: '903.03' }), na]),
    ])
    expect(columns).toHaveLength(2)
    expect(rows.map((r) => r.id)).toEqual(['min_lot_size'])
    expect(rows[0].sections).toEqual(['903.03', '925.01.C.2'])
  })
})
