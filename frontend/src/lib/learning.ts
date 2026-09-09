export type Strictness = 0 | 1 | 2

export const STRICTNESS_LABEL: Record<Strictness, string> = {
  0: 'Conservative',
  1: 'Balanced',
  2: 'Adventurous',
}

export const STRICTNESS_HELP: Record<Strictness, string> = {
  0: 'Fewer matches, higher precision',
  1: 'Balanced',
  2: 'More matches, higher recall',
}

export const PERIOD_KEY = 'ajas_learning_period'

export function loadPeriod(): '7d' | '30d' {
  const value = localStorage.getItem(PERIOD_KEY)
  return value === '30d' ? '30d' : '7d'
}

export function savePeriod(period: '7d' | '30d') {
  localStorage.setItem(PERIOD_KEY, period)
}

export function asStrictness(value: number): Strictness {
  if (value <= 0) return 0
  if (value >= 2) return 2
  return 1
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}
