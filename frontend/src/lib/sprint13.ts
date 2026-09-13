import { windowedRange } from './jobs'
import { isPhoneLayout } from './responsive'

export const BOTTOM_NAV = [
  { href: '#/jobs', label: 'Jobs' },
  { href: '#/review', label: 'Review' },
  { href: '#/apply', label: 'Apply' },
  { href: '#/email', label: 'Mail' },
  { href: '#/settings', label: 'More' },
] as const

export type RedactionField = 'email' | 'phone' | 'resume'
const REDACT_KEY = 'ajas.s13.redact'

export function explanationChips(reasons: string[]): { label: string; detail: string }[] {
  return reasons.map((label) => ({ label, detail: `Matched on ${label}` }))
}

export function diffLineClass(line: string): string {
  if (line.startsWith('+') && !line.startsWith('+++')) return 'jd-diff-line add'
  if (line.startsWith('-') && !line.startsWith('---')) return 'jd-diff-line del'
  return 'jd-diff-line'
}

export function virtualWindow10k(
  total: number,
  scrollTop: number,
  viewport: number,
): { start: number; end: number; virtualized: boolean } {
  const range = windowedRange(total, scrollTop, viewport, 36, 12)
  return { start: range.start, end: range.end, virtualized: total >= 10_000 }
}

export function shouldRefreshSearch(ageMin: number, staleAfterMin: number): { refresh: boolean; notify: boolean } {
  const refresh = ageMin >= staleAfterMin
  return { refresh, notify: refresh }
}

export function swipeNav(dx: number, hrefs: readonly string[], current: string): string | null {
  if (Math.abs(dx) < 40) return null
  const index = hrefs.indexOf(current)
  if (index < 0) return null
  const next = dx < 0 ? index + 1 : index - 1
  return hrefs[Math.max(0, Math.min(hrefs.length - 1, next))] ?? null
}

export function loadRedactionFields(): RedactionField[] {
  if (typeof localStorage === 'undefined') return ['email']
  try {
    const raw = localStorage.getItem(REDACT_KEY)
    const parsed = raw ? (JSON.parse(raw) as RedactionField[]) : ['email']
    return parsed.filter((item) => item === 'email' || item === 'phone' || item === 'resume')
  } catch {
    return ['email']
  }
}

export function saveRedactionFields(fields: RedactionField[]): RedactionField[] {
  if (typeof localStorage !== 'undefined') localStorage.setItem(REDACT_KEY, JSON.stringify(fields))
  return fields
}

export function applyRedaction<T extends Record<string, unknown>>(payload: T, fields: RedactionField[]): T {
  const out = { ...payload }
  for (const field of fields) {
    if (field in out) (out as Record<string, unknown>)[field] = '[redacted]'
  }
  return out
}

export function showBottomNav(width: number): boolean {
  return isPhoneLayout(width)
}

export function sprint13Changelog(): { version: string; highlights: string[] }[] {
  return [
    {
      version: '13.0.0',
      highlights: ['Canary rollouts', 'Match chips', 'Mobile bottom nav', 'Adapter v3 guards'],
    },
  ]
}

export function gestureSwipe(startX: number, endX: number): 'left' | 'right' | null {
  const dx = endX - startX
  if (Math.abs(dx) < 40) return null
  return dx < 0 ? 'left' : 'right'
}
