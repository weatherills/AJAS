import { CURRENT_VERSIONS } from '../lib/matching'
import { json, request } from './live'
import type { MatchingApi, MatchView } from './matchingTypes'

type ComputeBody = {
  score: number
  breakdown?: { keyword: number; semantic: number; weights?: { keyword: number; semantic: number } }
  explanation?: string
  persisted: boolean
  matchId?: string
  thresholdUsed?: number
  versions?: MatchView['versions']
  input?: { resumeId?: string; jobId?: string }
  jobId?: string
  idx?: number
  error?: string
}

function mapResult(jobId: string, resumeId: string | null, row: ComputeBody): MatchView {
  if (row.error) {
    return {
      jobId,
      resumeId,
      score: null,
      state: 'error',
      breakdown: null,
      terms: [],
      explanation: '',
      versions: row.versions || CURRENT_VERSIONS,
      computedAt: new Date().toISOString(),
      persisted: false,
      error: row.error,
    }
  }
  const weights = row.breakdown?.weights || { keyword: 0.4, semantic: 0.6 }
  return {
    jobId,
    resumeId,
    score: row.score,
    state: 'computed',
    breakdown: row.breakdown
      ? { keyword: row.breakdown.keyword, semantic: row.breakdown.semantic, weights }
      : null,
    terms: [],
    explanation: row.explanation || '',
    versions: row.versions || CURRENT_VERSIONS,
    computedAt: new Date().toISOString(),
    persisted: Boolean(row.persisted),
    matchId: row.matchId,
  }
}

async function waitForOperation(operationId: string) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const op = await json<{
      status: string
      error?: string
      results?: ComputeBody[]
      result?: ComputeBody
    }>(await request(`/api/v1/operations/${encodeURIComponent(operationId)}`))
    if (op.status === 'completed') return op
    if (op.status === 'failed') throw new Error(op.error || 'Match failed')
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error('Match timed out')
}

export const liveMatchingApi: MatchingApi = {
  async scoreMany(query) {
    if (!query.resumeId) {
      return query.jobs.map((job) => ({
        jobId: job.id,
        resumeId: null,
        score: null,
        state: 'no_resume' as const,
        breakdown: null,
        terms: [],
        explanation: '',
        versions: null,
        computedAt: null,
        persisted: false,
      }))
    }
    const resp = await request('/api/v1/matches/rank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resumeId: query.resumeId,
        resumeText: query.resumeText,
        jobIds: query.jobs.map((job) => job.id),
        jobTexts: query.jobs.map((job) => job.text),
        threshold: query.threshold,
        explanation: query.explanation !== false,
        persist: query.persist === true,
      }),
    })
    if (resp.status === 202) {
      const queued = await json<{ operationId: string }>(resp)
      const op = await waitForOperation(queued.operationId)
      const results = op.results || (op.result ? [op.result] : [])
      return query.jobs.map((job, index) => {
        const row = results.find((item) => item.jobId === job.id || item.idx === index) || results[index]
        if (!row) {
          return mapResult(job.id, query.resumeId, { score: 0, persisted: false, error: 'No score' })
        }
        return mapResult(job.id, query.resumeId, row)
      })
    }
    const body = await json<{ results: ComputeBody[] }>(resp)
    return query.jobs.map((job, index) => {
      const row = body.results?.find((item) => item.jobId === job.id || item.idx === index) || body.results?.[index]
      return mapResult(job.id, query.resumeId, row || { score: 0, persisted: false, error: 'No score' })
    })
  },
  async scoreOne(query) {
    const [row] = await liveMatchingApi.scoreMany({ ...query, jobs: [query.job] })
    return row
  },
}
