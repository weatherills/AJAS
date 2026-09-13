export type SiteLimit = { site: string; cap: number; consent: boolean; used: number }

export function evaluateLimit(row: SiteLimit): { allowed: boolean; reason: 'ok' | 'consent' | 'cap' } {
  if (!row.consent) return { allowed: false, reason: 'consent' }
  if (row.used >= row.cap) return { allowed: false, reason: 'cap' }
  return { allowed: true, reason: 'ok' }
}
