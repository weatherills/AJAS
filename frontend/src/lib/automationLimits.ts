export type SiteLimit = { site: string; cap: number; consent: boolean; used: number; windowMinutes?: number }

export function evaluateLimit(row: SiteLimit): { allowed: boolean; reason: 'ok' | 'consent' | 'cap' } {
  if (!row.consent) return { allowed: false, reason: 'consent' }
  if (row.used >= row.cap) return { allowed: false, reason: 'cap' }
  return { allowed: true, reason: 'ok' }
}

export function remainingInWindow(row: SiteLimit): number {
  return Math.max(0, row.cap - row.used)
}

export function windowLabel(row: SiteLimit): string {
  const minutes = row.windowMinutes && row.windowMinutes > 0 ? row.windowMinutes : 1440
  if (minutes >= 1440) return 'daily'
  return `${minutes}m`
}
