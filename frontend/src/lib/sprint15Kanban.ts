import { bulkDismiss, dismissSnackbar, undoDismiss, type DismissSnapshot } from './dismiss'
import type { ReviewFilters } from '../api/reviewTypes'
import { missingMustHaves, subScores } from './sprint14'
import { explanationChips } from './sprint13'
import { shortcuts } from './sprint15'
import { trapFocus } from './focusTrap'
import { auditCsv, type AuditRow } from './audit'
import { parseAllowlist, recordAllowlistAudit } from './allowlist'
import { buildExportBundle, purgeSummary } from './privacy'

const MEMORY = new Map<string, string>()

function readStore(key: string): string | null {
  try {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key)
  } catch {
    /* fall through */
  }
  return MEMORY.get(key) ?? null
}

function writeStore(key: string, value: string): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value)
      return
    }
  } catch {
    /* fall through */
  }
  MEMORY.set(key, value)
}

export const SELECT_KEY = 'ajas.review.selected.v2'
export const OVERRIDE_KEY = 'ajas.apply.siteOverrides.v1'
export const SUPPRESS_KEY = 'ajas.mail.suppressed.v1'

export type SiteOverride = { site: string; fields: Record<string, string> }

export function persistSelection(ids: string[]): string[] {
  writeStore(SELECT_KEY, JSON.stringify(ids))
  return ids
}

export function loadSelection(): string[] {
  try {
    const raw = readStore(SELECT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

export function shareFilterHref(filters: ReviewFilters, origin = ''): string {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.company) params.set('company', filters.company)
  if (filters.location) params.set('loc', filters.location)
  if (filters.minScore) params.set('min', String(filters.minScore))
  if (filters.maxScore !== 100) params.set('max', String(filters.maxScore))
  if (filters.source && filters.source !== 'all') params.set('source', filters.source)
  if (filters.sort && filters.sort !== 'score') params.set('sort', filters.sort)
  const qs = params.toString()
  return `${origin}#/review${qs ? `?${qs}` : ''}`
}

export function bulkDismissWithUndo(ids: string[], selected: string[]): DismissSnapshot & { snackbar: string } {
  const snap = bulkDismiss(ids, selected)
  return { ...snap, snackbar: dismissSnackbar(snap.dismissed.length) }
}

export function restoreDismiss(snap: DismissSnapshot, current: string[]): string[] {
  return undoDismiss(snap, current)
}

export function a11yShortcuts(): Record<string, string> {
  return { ...shortcuts(), '?': 'help', Escape: 'close' }
}

export function handleReviewKeydown(container: HTMLElement, event: KeyboardEvent): void {
  trapFocus(container, event)
}

export function fitSubScoreTooltips(keyword: number, semantic: number, recency: number) {
  const scores = subScores(keyword, semantic, recency)
  return {
    ...scores,
    tips: {
      keyword: 'Resume keywords overlapping the posting',
      semantic: 'Embedding similarity of resume vs job text',
      recency: 'How recently the role was posted or updated',
    },
  }
}

export function groupEvidence(highlights: string[], gaps: string[]): { skills: ReturnType<typeof explanationChips>; missing: string[] } {
  return { skills: explanationChips(highlights), missing: missingMustHaves([], gaps) }
}

export function truncateChip(label: string, max = 24): { label: string; detail: string } {
  const trimmed = label.trim()
  return { label: trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed, detail: trimmed }
}

export function manualPackageSteps(captcha: boolean): string[] {
  const steps = ['Copy posting URL', 'Open the employer site', 'Attach resume + cover letter', 'Mark submitted in AJAS']
  if (captcha) steps.unshift('Complete captcha in the browser — AJAS never bypasses it')
  return steps
}

export function loadSiteOverrides(): SiteOverride[] {
  try {
    const raw = readStore(OVERRIDE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as SiteOverride[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveSiteOverride(site: string, fields: Record<string, string>): SiteOverride[] {
  const next = [...loadSiteOverrides().filter((item) => item.site !== site), { site, fields }]
  writeStore(OVERRIDE_KEY, JSON.stringify(next))
  return next
}

export function validateOverride(fields: Record<string, string>): { missing: string[]; valid: boolean } {
  const missing = ['name', 'email', 'resume'].filter((key) => !fields[key])
  return { missing, valid: missing.length === 0 }
}

export function loadSuppressed(): string[] {
  try {
    const raw = readStore(SUPPRESS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as string[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function syncSuppressed(add: string[] = [], restore: string[] = []): string[] {
  const next = new Set(loadSuppressed().map((item) => item.toLowerCase()))
  for (const addr of add) next.add(addr.toLowerCase())
  for (const addr of restore) next.delete(addr.toLowerCase())
  const list = [...next].sort()
  writeStore(SUPPRESS_KEY, JSON.stringify(list))
  return list
}

export function exportAuditCsv(rows: AuditRow[]): string {
  return auditCsv(rows)
}

export function allowlistUpdate(actor: string, raw: string) {
  return { ...recordAllowlistAudit(actor, raw), hosts: parseAllowlist(raw) }
}

export function gdprDownload(userId: string) {
  return buildExportBundle(userId)
}

export function forgetPreview(userId: string) {
  return { ...purgeSummary(gdprDownload(userId)), dryRun: true }
}

export function slaWidgets(matchP95: number, ingestRps: number, applyOk: number) {
  return {
    matchP95,
    matchP99: Math.round(matchP95 * 1.4),
    ingestRps,
    applySuccess: applyOk,
    ok: matchP95 < 2500 && applyOk >= 0.9,
  }
}
