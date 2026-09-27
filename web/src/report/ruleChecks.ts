import type { ProgramEvaluation, RuleCheck } from '../models/report'

const UNIT: Record<string, string> = { sf: 'sq ft', ft: 'ft' }

function n(value: number): string {
  return Math.round(value).toLocaleString('en-US')
}

/** How far the lot falls short of what the rule requires: "27% short". */
export function shortfall(check: RuleCheck): string {
  const { required, provided } = check
  if (required === null || provided === null || required <= 0 || provided >= required) return ''
  return `${Math.round(100 * (1 - provided / required))}% short`
}

/** What the rule requires next to what the lot provides, for a passing check. */
export function measure(check: RuleCheck): string {
  const { required, provided } = check
  if (required === null || provided === null) return ''
  const unit = UNIT[check.unit ?? ''] ?? check.unit ?? ''
  switch (check.id) {
    case 'fits_envelope':
      return `needs ${n(required)} ${unit} · room for ${n(provided)}`
    case 'min_lot_size':
      return `${n(provided)} ${unit} lot · min ${n(required)}`
    case 'row_fits_width':
      return `${n(required)} ${unit} row · ${n(provided)} ${unit} lot`
    default:
      return `needs ${n(required)} ${unit} · has ${n(provided)}`
  }
}

/** The line under a table cell. */
export function checkDetail(check: RuleCheck): string {
  switch (check.status) {
    case 'pass':
      return measure(check)
    case 'needs_approval':
      return shortfall(check) || measure(check)
    case 'rejected':
      return check.relief === 'use_variance' ? 'use not allowed' : shortfall(check)
    default:
      return ''
  }
}

/**
 * The table: one column per building type the engine marks representative (plus the report's
 * options), one row per rule, in the order the engine lists them, skipping rules that apply to
 * none of the columns.
 */
export function ruleTable(programs: ProgramEvaluation[]) {
  const columns = programs.filter((p) => p.representative || p.chosenAs)
  const ids: string[] = []
  for (const p of columns) for (const c of p.checks) if (!ids.includes(c.id)) ids.push(c.id)
  const rows = ids
    .map((id) => ({ id, cells: columns.map((p) => p.checks.find((c) => c.id === id) ?? null) }))
    .filter((row) => row.cells.some((c) => c && c.status !== 'not_applicable'))
    .map((row) => {
      const first = row.cells.find((c) => c !== null)!
      const sections = [...new Set(row.cells.map((c) => c?.section).filter(Boolean))].sort()
      return { ...row, label: first.label, sections: sections as string[] }
    })
  return { columns, rows }
}
