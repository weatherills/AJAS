import { json, request } from './live'
import type { ReviewApi, ReviewDecision, ReviewMatch, ReviewStatus } from './reviewTypes'
import { applyFilters } from '../lib/review'

type ApiMatch = {
  matchId: string
  jobId: string
  resumeId: string | null
  jobTitle: string
  company: string
  location: string
  score: number | null
  suggestion: string
  status: string
  source: string
  createdAt: string
  updatedAt: string
  queuedAt?: string
  etag: string
  summary?: string | null
  why?: string | null
  highlights?: string[] | null
  decidedAt?: string | null
  latestDecisionId?: string | null
}

function mapStatus(status: string): ReviewStatus {
  if (status === 'approved') return 'approved'
  if (status === 'rejected') return 'rejected'
  return 'pending'
}

function mapMatch(row: ApiMatch, extra: Partial<ReviewMatch> = {}): ReviewMatch {
  const status = mapStatus(row.status)
  return {
    matchId: row.matchId,
    jobId: row.jobId,
    resumeId: row.resumeId,
    jobTitle: row.jobTitle,
    company: row.company,
    location: row.location,
    score: row.score,
    suggestion: (row.suggestion as ReviewMatch['suggestion']) || 'none',
    status,
    source: row.source === 'saved' ? 'saved' : 'ai',
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    queuedAt: row.queuedAt || row.createdAt,
    etag: row.etag,
    postingUrl: null,
    applied: status === 'approved',
    summary: row.summary ?? null,
    why: row.why ?? null,
    highlights: row.highlights ?? null,
    resumeHighlights: null,
    decidedAt: row.decidedAt ?? null,
    latestDecisionId: row.latestDecisionId ?? null,
    comment: extra.comment ?? null,
    decision: extra.decision ?? null,
    scoreAtDecision: extra.scoreAtDecision ?? null,
  }
}

async function fetchMatches(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const data = await json<{ items: ApiMatch[]; continuationToken?: string }>(
    await request(`/api/v1/matches?${search.toString()}`),
  )
  return (data.items || []).map((row) => mapMatch(row))
}

export const liveReviewApi: ReviewApi = {
  async list(tab, filters) {
    const status =
      tab === 'history'
        ? undefined
        : filters.status === 'awaiting'
          ? 'pending'
          : filters.status === 'all'
            ? undefined
            : filters.status
    const source = tab === 'saved' ? 'saved' : tab === 'matches' && filters.source === 'all' ? 'ai' : filters.source === 'all' ? undefined : filters.source
    if (tab === 'history') {
      const approved = await fetchMatches({ status: 'approved', pageSize: 100 })
      const rejected = await fetchMatches({ status: 'rejected', pageSize: 100 })
      const merged = [...approved, ...rejected]
      const withDecisions = await Promise.all(
        merged.map(async (row) => {
          const hist = await json<{ items: ReviewDecision[] }>(
            await request(`/api/v1/decisions/history?matchId=${encodeURIComponent(row.matchId)}`),
          )
          const latest = hist.items?.[hist.items.length - 1]
          return {
            ...row,
            comment: latest?.comment ?? null,
            decision: latest?.decision ?? (row.status === 'approved' ? 'approve' : 'reject'),
            scoreAtDecision: latest?.aiScore ?? row.score,
            decidedAt: latest?.createdAt ?? row.decidedAt,
          }
        }),
      )
      const items = applyFilters(withDecisions, tab, filters)
      return { items, total: items.length }
    }
    const rows = await fetchMatches({
      status,
      source,
      minScore: filters.minScore,
      company: filters.company,
      location: filters.location,
      createdAfter: filters.createdAfter,
      pageSize: 100,
    })
    const items = applyFilters(rows, tab, { ...filters, source: tab === 'saved' ? 'saved' : filters.source })
    return { items, total: items.length }
  },
  async get(matchId, opts) {
    const body = await json<{
      match: ApiMatch
      decision?: ReviewDecision | null
      blobs?: { jobUrl?: string | null; resumeUrl?: string | null }
    }>(await request(`/api/v1/matches/${encodeURIComponent(matchId)}`))
    let decision = body.decision || null
    if (opts?.decisionId) {
      const hist = await json<{ items: ReviewDecision[] }>(
        await request(`/api/v1/decisions/history?matchId=${encodeURIComponent(matchId)}`),
      )
      decision = hist.items.find((item) => item.decisionId === opts.decisionId) || null
    }
    return {
      match: mapMatch(body.match, {
        comment: decision?.comment ?? null,
        decision: decision?.decision ?? null,
        scoreAtDecision: decision?.aiScore ?? null,
      }),
      decision,
      blobs: { jobUrl: body.blobs?.jobUrl ?? null, resumeUrl: body.blobs?.resumeUrl ?? null },
      snapshotUnavailable: Boolean(opts?.decisionId && !decision),
    }
  },
  async decide(matchId, body, meta) {
    const resp = await request(`/api/v1/matches/${encodeURIComponent(matchId)}/decision`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': meta.idempotencyKey,
        'If-Match': meta.etag,
      },
      body: JSON.stringify(body),
    })
    return json(resp)
  },
  async reopen(matchId) {
    return json(await request(`/api/v1/matches/${encodeURIComponent(matchId)}/reopen`, { method: 'POST' }))
  },
}
