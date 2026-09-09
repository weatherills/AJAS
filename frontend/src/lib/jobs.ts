import type { JobCard, JobFilters, JobListQuery, JobSourceName, JobSourceRef, SourceStatus } from '../api/jobsTypes'

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

export function loadFilters(): JobFilters {
  try {
    const raw = localStorage.getItem(FILTER_KEY)
    if (!raw) return defaultFilters()
    const parsed = JSON.parse(raw) as Partial<JobFilters>
    const sources = (parsed.sources || []).filter((item): item is JobSourceName => item === 'greenhouse' || item === 'lever')
    return {
      sources: sources.length ? sources : [...ALL_SOURCES],
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
  if (row.status === 'syncing') return row.progress ? `Syncing… ${row.progress}` : 'Syncing…'
  if (row.status === 'rate_limited') {
    const left = backoffRemainingMs(row.backoffUntil, now)
    return left > 0 ? `Temporarily limited ${formatCountdown(left)}` : 'Temporarily limited'
  }
  if (row.status === 'error') return 'Error'
  return 'OK'
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
  if (query.sources.length && !job.sources.some((item) => query.sources.includes(item.source))) return false
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
