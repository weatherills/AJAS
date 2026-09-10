import type {
  AddTenantResult,
  JobCard,
  JobFilters,
  JobListQuery,
  JobSourceName,
  JobSourceRef,
  SourceBoard,
  SourceStatus,
} from '../api/jobsTypes'
import type { SettingsApi } from '../api/settingsTypes'

const FILTER_KEY = 'ajas.jobFeed.filters'
const VISIT_KEY = 'ajas.jobFeed.lastVisit'

export const PAGE_SIZE = 25
export const ALL_SOURCES: JobSourceName[] = ['greenhouse', 'lever']

const SLUG = /[^a-z0-9]+/g

export function slug(value: string | null | undefined): string {
  const text = (value || '').trim().toLowerCase().replace(SLUG, '-').replace(/^-|-$/g, '')
  return text || 'unknown'
}

export function canonicalKey(title: string, location: string, company: string): string {
  return `${slug(title)}|${slug(location)}|${slug(company)}`
}

export function sourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function defaultFilters(): JobFilters {
  return { sources: [...ALL_SOURCES], q: '', location: '', status: 'all', pagination: 'infinite' }
}

export function clearSessionFilters(filters: JobFilters): JobFilters {
  return { ...defaultFilters(), sources: [...filters.sources] }
}

export function loadFilters(): JobFilters {
  try {
    const raw = localStorage.getItem(FILTER_KEY)
    if (!raw) return defaultFilters()
    const parsed = JSON.parse(raw) as Partial<JobFilters>
    const sources = Array.isArray(parsed.sources)
      ? parsed.sources.filter((item): item is JobSourceName => item === 'greenhouse' || item === 'lever')
      : [...ALL_SOURCES]
    return {
      sources,
      q: typeof parsed.q === 'string' ? parsed.q : '',
      location: typeof parsed.location === 'string' ? parsed.location : '',
      status: parsed.status === 'new' ? 'new' : 'all',
      pagination: parsed.pagination === 'pages' ? 'pages' : 'infinite',
    }
  } catch {
    return defaultFilters()
  }
}

export function saveFilters(filters: JobFilters): void {
  localStorage.setItem(FILTER_KEY, JSON.stringify(filters))
}

export function takeLastVisit(): string {
  const previous = localStorage.getItem(VISIT_KEY)
  const stamp = new Date().toISOString()
  localStorage.setItem(VISIT_KEY, stamp)
  return previous || stamp
}

export function formatWhen(stamp: string | null): string {
  if (!stamp) return 'Never'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return date.toLocaleString()
}

export function backoffRemainingMs(until: string | null, now = Date.now()): number {
  if (!until) return 0
  const end = new Date(until).getTime()
  if (Number.isNaN(end)) return 0
  return Math.max(0, end - now)
}

export function formatCountdown(ms: number): string {
  const total = Math.ceil(ms / 1000)
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function statusLabel(row: SourceStatus, now = Date.now()): string {
  if (row.status === 'unconfigured' || row.configured === false) return 'Not configured'
  if (row.status === 'syncing') return row.progress ? `Syncing… ${row.progress}` : 'Syncing…'
  if (row.status === 'rate_limited') {
    const left = backoffRemainingMs(row.backoffUntil, now)
    return left > 0 ? `Temporarily limited ${formatCountdown(left)}` : 'Temporarily limited'
  }
  if (row.status === 'error') {
    const copy = sourceErrorCopy(row) || ''
    if (/not found/i.test(copy)) return 'Board not found'
    if (/unreachable/i.test(copy)) return 'Unreachable'
    return 'Error'
  }
  return 'OK'
}

export function sourceIsConfiguredStatus(row: Pick<SourceStatus, 'status' | 'configured'> | undefined): boolean {
  if (!row) return true
  if (row.status === 'unconfigured') return false
  return row.configured !== false
}

export function sourceUnconfiguredCopy(row: Pick<SourceStatus, 'source' | 'status' | 'errorMessage' | 'configured'>): string | null {
  if (sourceIsConfiguredStatus(row)) return null
  const raw = (row.errorMessage || '').trim()
  if (raw) return raw
  return `${sourceTitle(row.source)} is not configured. Add a board token before turning this source on, or Job Feed stays empty.`
}

export function sourceErrorCopy(row: Pick<SourceStatus, 'source' | 'status' | 'errorMessage'>): string | null {
  if (row.status !== 'error') return null
  const name = sourceTitle(row.source)
  const raw = (row.errorMessage || '').trim()
  if (!raw) return `${name} fetch failed.`
  return raw
}

export function boardErrorCopy(
  board: Pick<SourceBoard, 'tenantKey' | 'status' | 'errorMessage'>,
  source: Pick<SourceStatus, 'source' | 'status' | 'errorMessage'>,
  boardCount = 1,
): string | null {
  const own = (board.errorMessage || '').trim()
  if (own && (board.status === 'error' || /not found|unreachable|fetch failed|returned HTTP/i.test(own))) {
    return own
  }
  if (board.status === 'error') {
    return sourceErrorCopy(source) || `${sourceTitle(source.source)} fetch failed.`
  }
  const sourceCopy = sourceErrorCopy(source)
  if (!sourceCopy) return null
  const key = (board.tenantKey || '').trim().toLowerCase()
  if (key && sourceCopy.toLowerCase().includes(key)) return sourceCopy
  if (boardCount === 1) return sourceCopy
  return null
}

export function sourceBoardErrors(
  row: Pick<SourceStatus, 'source' | 'status' | 'errorMessage' | 'boards'>,
): { tenantKey: string; message: string }[] {
  const boards = row.boards || []
  const lines: { tenantKey: string; message: string }[] = []
  for (const board of boards) {
    const message = boardErrorCopy(board, row, boards.length)
    if (message) lines.push({ tenantKey: board.tenantKey, message })
  }
  return lines
}

export function sourceListFingerprint(rows: SourceStatus[]): string {
  return [...rows]
    .map((row) => {
      const boards = [...(row.boards || [])]
        .map((board) => [board.tenantKey, board.enabled ? '1' : '0', board.status ?? '', board.lastSyncAt ?? ''].join(':'))
        .sort()
        .join(',')
      return [
        row.source,
        row.status,
        row.lastSyncAt ?? '',
        row.backoffUntil ?? '',
        row.configured === false ? '0' : '1',
        String(row.tenantCount ?? ''),
        boards,
      ].join('|')
    })
    .sort()
    .join('\n')
}

export function jobsListMayHaveChanged(previous: string | null, next: string): boolean {
  return previous != null && previous !== next
}

export function nextSourcePollMs(syncing: boolean, current: number): number {
  if (syncing) return 5_000
  if (!current || current < 15_000) return 15_000
  return Math.min(60_000, current * 1.5)
}

export function feedErrorLines(rows: SourceStatus[]): { key: string; message: string }[] {
  const lines: { key: string; message: string }[] = []
  for (const row of rows) {
    const boards = sourceBoardErrors(row)
    if (boards.length) {
      for (const board of boards) {
        lines.push({ key: `${row.source}:${board.tenantKey}`, message: board.message })
      }
      continue
    }
    const copy = sourceErrorCopy(row)
    if (copy) lines.push({ key: row.source, message: copy })
  }
  return lines
}

export function addBoardToast(
  source: JobSourceName,
  result: Pick<AddTenantResult, 'tenantKey' | 'status'>,
): { text: string; tone: 'info' | 'error' } {
  const row = result.status
  const boards = row?.boards || []
  const board = boards.find((item) => item.tenantKey === result.tenantKey)
  if (row && board) {
    const err = boardErrorCopy(board, row, boards.length)
    if (err) return { text: err, tone: 'error' }
  }
  if (row) {
    const err = sourceErrorCopy(row)
    if (err) return { text: err, tone: 'error' }
  }
  return { text: `${sourceTitle(source)} board “${result.tenantKey}” added`, tone: 'info' }
}

export function refreshToastForStatuses(
  source: JobSourceName | 'all',
  rows: SourceStatus[],
  added: number,
): { text: string; tone: 'info' | 'error'; live: string } {
  const targeted = rows.filter((item) => source === 'all' || item.source === source)
  const missing = targeted.filter((item) => !sourceIsConfiguredStatus(item))
  if (missing.length) {
    const text = missing.map((item) => sourceUnconfiguredCopy(item) || `${sourceTitle(item.source)} is not configured.`).join(' ')
    return { text, tone: 'error', live: 'Source not configured' }
  }
  const failed = targeted.filter((item) => item.status === 'error')
  if (failed.length) {
    const text = feedErrorLines(failed)
      .map((item) => item.message)
      .join(' ')
    return {
      text: text || failed.map((item) => sourceErrorCopy(item) || `${sourceTitle(item.source)} fetch failed.`).join(' '),
      tone: 'error',
      live: 'Sync error',
    }
  }
  const label = source === 'all' ? 'Sources' : sourceTitle(source)
  const text = added > 0 ? `${label} updated: ${added} new job${added === 1 ? '' : 's'}` : `${label}: no new jobs.`
  return { text, tone: 'info', live: 'Syncing completed' }
}

export function mergeJobs(items: JobCard[]): JobCard[] {
  const byKey = new Map<string, JobCard>()
  for (const item of items) {
    const existing = byKey.get(item.canonicalKey)
    if (!existing) {
      byKey.set(item.canonicalKey, {
        ...item,
        sources: [...item.sources],
      })
      continue
    }
    const sources = [...existing.sources]
    for (const ref of item.sources) {
      if (!sources.some((entry) => entry.source === ref.source && entry.sourceUrl === ref.sourceUrl)) {
        sources.push(ref)
      }
    }
    const newer = item.updatedAt > existing.updatedAt ? item : existing
    byKey.set(item.canonicalKey, {
      ...newer,
      id: existing.id,
      sources,
      isNew: existing.isNew || item.isNew,
      primarySource: newer.primarySource,
    })
  }
  return [...byKey.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

export function matchesQuery(job: JobCard, query: JobListQuery): boolean {
  if (!job.sources.some((item) => query.sources.includes(item.source))) return false
  const haystack = `${job.title} ${job.location} ${job.company}`.toLowerCase()
  if (query.q && !haystack.includes(query.q.trim().toLowerCase())) return false
  if (query.location && !job.location.toLowerCase().includes(query.location.trim().toLowerCase())) return false
  if (query.status === 'new' && !job.isNew) return false
  return true
}

export function paginate<T>(items: T[], cursor: string | null, limit: number): { items: T[]; nextCursor: string | null } {
  const start = cursor ? Number.parseInt(cursor, 10) || 0 : 0
  const slice = items.slice(start, start + limit)
  const next = start + slice.length
  return { items: slice, nextCursor: next < items.length ? String(next) : null }
}

export function alsoFromLabel(sources: JobSourceRef[], primary: JobSourceName): string | null {
  const others = sources.filter((item) => item.source !== primary)
  if (!others.length) return null
  const names = [...new Set(others.map((item) => (item.source === 'greenhouse' ? 'Greenhouse' : 'Lever')))]
  if (names.length === 1) return `Also found on ${names[0]}`
  return `Also found on ${names.join(' and ')}`
}

export function sourceTitle(source: JobSourceName): string {
  return source === 'greenhouse' ? 'Greenhouse' : 'Lever'
}

export function boardInputHint(source: JobSourceName): string {
  return source === 'greenhouse'
    ? 'Board token or https://boards.greenhouse.io/… URL'
    : 'Company slug or https://jobs.lever.co/… URL'
}

export function boardAddPayload(raw: string): { boardToken?: string; boardUrl?: string } {
  const value = raw.trim()
  if (!value) return {}
  if (/^https?:\/\//i.test(value)) return { boardUrl: value }
  return { boardToken: value }
}

export function sourcesOffCopy(): string {
  return 'Job sources are turned off in Settings, so the feed is empty even if boards are configured.'
}

export function feedSourcesFromSettings(sources: {
  greenhouseEnabled?: boolean
  leverEnabled?: boolean
  greenhouseConfigured?: boolean
  leverConfigured?: boolean
}): JobSourceName[] | null {
  // Missing configured flags means settings did not see job-source wiring; keep current filters.
  if (sources.greenhouseConfigured === undefined && sources.leverConfigured === undefined) {
    return null
  }
  const next: JobSourceName[] = []
  if (sources.greenhouseEnabled) next.push('greenhouse')
  if (sources.leverEnabled) next.push('lever')
  return next
}

export function sourceEnabledField(name: JobSourceName): 'greenhouseEnabled' | 'leverEnabled' {
  return name === 'greenhouse' ? 'greenhouseEnabled' : 'leverEnabled'
}

export function sourceChipPatch(
  name: JobSourceName,
  enabled: boolean,
): { sources: { greenhouseEnabled?: boolean; leverEnabled?: boolean } } {
  return { sources: { [sourceEnabledField(name)]: enabled } }
}

export function nextFeedSources(current: JobSourceName[], name: JobSourceName): { sources: JobSourceName[]; enabled: boolean } {
  const on = current.includes(name)
  return {
    sources: on ? current.filter((item) => item !== name) : [...current, name],
    enabled: !on,
  }
}

export function feedSourcesQueryParam(sources: JobSourceName[]): string {
  return sources.join(',') || 'none'
}

export async function persistFeedSourceChip(
  api: Pick<SettingsApi, 'patch'>,
  name: JobSourceName,
  enabled: boolean,
): Promise<JobSourceName[] | null> {
  const doc = await api.patch(sourceChipPatch(name, enabled))
  return feedSourcesFromSettings(doc.sources)
}
