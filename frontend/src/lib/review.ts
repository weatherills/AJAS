import type { ReviewApi, ReviewFilters, ReviewMatch, ReviewStatus, ReviewTab, Suggestion } from '../api/reviewTypes'

export const COMMENT_MAX = 1000
export const WHY_MAX = 400
export const PAGE_SIZE = 25

export const DEFAULT_FILTERS: ReviewFilters = {
  minScore: 0,
  maxScore: 100,
  company: '',
  location: '',
  source: 'all',
  status: 'awaiting',
  createdAfter: '',
  sort: 'score',
}

export function validateComment(raw: string): { value: string; error: string | null; remaining: number } {
  const value = raw.replace(/^\s+/, '')
  if (value.length > COMMENT_MAX) {
    return {
      value: value.slice(0, COMMENT_MAX),
      error: `Comments can be at most ${COMMENT_MAX} characters.`,
      remaining: 0,
    }
  }
  return { value, error: null, remaining: COMMENT_MAX - value.length }
}

export function suggestionLabel(suggestion: Suggestion): string {
  if (suggestion === 'approve') return 'Recommend Approve'
  if (suggestion === 'reject') return 'Recommend Reject'
  if (suggestion === 'review') return 'Recommend Review'
  return 'No suggestion available'
}

export function statusLabel(status: ReviewStatus): string {
  if (status === 'pending') return 'Awaiting decision'
  if (status === 'approved') return 'Approved'
  return 'Rejected'
}

export function sourceLabel(source: 'ai' | 'saved'): string {
  return source === 'ai' ? 'AI' : 'Saved'
}

export function truncateText(text: string | null | undefined, max: number): { text: string; truncated: boolean } {
  const value = (text || '').trim()
  if (value.length <= max) return { text: value, truncated: false }
  const sliced = value.slice(0, max)
  const boundary = sliced.lastIndexOf(' ')
  const cut = boundary > max * 0.6 ? sliced.slice(0, boundary) : sliced
  return { text: cut.replace(/\s+$/, ''), truncated: true }
}

export function formatWhen(stamp: string | null | undefined): string {
  if (!stamp) return '—'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDay(stamp: string | null | undefined): string {
  if (!stamp) return '—'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return date.toLocaleDateString()
}

function statusMatches(status: ReviewStatus, filter: ReviewFilters['status']): boolean {
  if (filter === 'all') return true
  if (filter === 'awaiting') return status === 'pending'
  return status === filter
}

export function applyFilters(items: ReviewMatch[], tab: ReviewTab, filters: ReviewFilters): ReviewMatch[] {
  const scoped = items.filter((item) => {
    if (tab === 'matches' && filters.source === 'all' && item.source !== 'ai') return false
    if (tab === 'saved' && item.source !== 'saved') return false
    if (tab === 'history') return item.status === 'approved' || item.status === 'rejected'
    return true
  })
  const filtered = scoped.filter((item) => {
    if (tab !== 'history' && !statusMatches(item.status, filters.status)) return false
    if (filters.source !== 'all' && item.source !== filters.source) return false
    const score = item.scoreAtDecision ?? item.score
    if (score != null && (score < filters.minScore || score > filters.maxScore)) return false
    if (score == null && (filters.minScore > 0 || filters.maxScore < 100) && tab !== 'saved') return false
    if (filters.company && !item.company.toLowerCase().includes(filters.company.toLowerCase())) return false
    if (filters.location && !item.location.toLowerCase().includes(filters.location.toLowerCase())) return false
    if (filters.createdAfter) {
      const stamp = item.queuedAt || item.createdAt
      if (stamp.slice(0, 10) < filters.createdAfter) return false
    }
    return true
  })
  const sorted = [...filtered]
  sorted.sort((a, b) => {
    if (filters.sort === 'company') return a.company.localeCompare(b.company)
    if (filters.sort === 'title') return a.jobTitle.localeCompare(b.jobTitle)
    if (filters.sort === 'date') {
      const left = tab === 'history' ? b.decidedAt || b.createdAt : b.queuedAt || b.createdAt
      const right = tab === 'history' ? a.decidedAt || a.createdAt : a.queuedAt || a.createdAt
      return left.localeCompare(right)
    }
    const scoreA = (tab === 'history' ? a.scoreAtDecision : a.score) ?? -1
    const scoreB = (tab === 'history' ? b.scoreAtDecision : b.score) ?? -1
    return scoreB - scoreA
  })
  return sorted
}

export function nextAfterRemove(ids: string[], currentId: string): string | null {
  const index = ids.indexOf(currentId)
  if (index < 0) return ids[0] || null
  return ids[index + 1] || ids[index - 1] || null
}

export function companiesFrom(items: ReviewMatch[]): string[] {
  return [...new Set(items.map((item) => item.company).filter(Boolean))].sort()
}

export function filtersForTab(tab: ReviewTab): ReviewFilters {
  return {
    ...DEFAULT_FILTERS,
    status: tab === 'history' ? 'all' : 'awaiting',
    source: tab === 'saved' ? 'saved' : tab === 'matches' ? 'ai' : 'all',
  }
}

export function tabForMatch(match: Pick<ReviewMatch, 'status' | 'source'>): ReviewTab {
  if (match.status === 'approved' || match.status === 'rejected') return 'history'
  if (match.source === 'saved') return 'saved'
  return 'matches'
}

export async function findReviewRow(
  api: ReviewApi,
  opts: { matchId?: string | null; jobId?: string | null; resumeId?: string | null },
): Promise<{ tab: ReviewTab; match: ReviewMatch } | null> {
  if (opts.matchId) {
    try {
      const detail = await api.get(opts.matchId)
      return { tab: tabForMatch(detail.match), match: detail.match }
    } catch {
      return null
    }
  }
  const tabs: ReviewTab[] = ['matches', 'saved', 'history']
  for (const tab of tabs) {
    const result = await api.list(tab, filtersForTab(tab))
    const match = result.items.find((item) => {
      if (opts.jobId && item.jobId === opts.jobId) return true
      if (opts.resumeId && item.resumeId === opts.resumeId) return true
      return false
    })
    if (match) return { tab, match }
  }
  return null
}
