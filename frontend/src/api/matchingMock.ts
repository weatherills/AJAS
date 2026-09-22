import {
  combineScore,
  CURRENT_VERSIONS,
  explanationFor,
  keywordOverlap,
  matchedTerms,
  tokenize,
} from '../lib/matching'
import type { MatchingApi, MatchView } from './matchingTypes'
import { mockLearningSnapshot } from './learningMock'
import { upsertMockReviewMatch } from './reviewMock'

function now() {
  return new Date().toISOString()
}

const persisted: Record<string, MatchView> = {}

function titleSignals(text: string): { keyword: number; semantic: number } {
  const title = (text.split('\n')[0] || text).toLowerCase()
  if (title.includes('designer')) return { keyword: 14, semantic: 10 }
  if (title.includes('manager')) return { keyword: 52, semantic: 61 }
  if (title.includes('staff') || title.includes('platform') || title.includes('security') || title.includes('data')) {
    return { keyword: 86, semantic: 90 }
  }
  if (title.includes('backend') || title.includes('frontend') || title.includes('engineer')) {
    return { keyword: 58, semantic: 72 }
  }
  return { keyword: 28, semantic: 34 }
}

function scoreOne(
  resumeText: string,
  resumeId: string | null,
  job: { id: string; text: string },
  threshold: number,
  persist = false,
): MatchView {
  if (!resumeId) {
    return {
      jobId: job.id,
      resumeId: null,
      score: null,
      state: 'no_resume',
      breakdown: null,
      terms: [],
      explanation: '',
      versions: null,
      computedAt: null,
      persisted: false,
    }
  }
  if (!job.text || job.text.trim().length < 30) {
    return {
      jobId: job.id,
      resumeId,
      score: null,
      state: 'insufficient',
      breakdown: null,
      terms: [],
      explanation: '',
      versions: CURRENT_VERSIONS,
      computedAt: now(),
      persisted: false,
    }
  }
  const overlapKeyword = keywordOverlap(resumeText, job.text)
  const overlapSemantic = keywordOverlap(resumeText, `${job.text.split('\n')[0] || job.text} ${job.text}`)
  const seeded = titleSignals(job.text)
  const keyword = Math.max(overlapKeyword, seeded.keyword)
  const semantic = Math.max(overlapSemantic, seeded.semantic)
  const weights = mockLearningSnapshot().weights
  const score = combineScore(keyword, semantic, weights.keyword, weights.semantic)
  const terms = matchedTerms(resumeText, job.text, 8)
  const gaps = tokenize(job.text).filter((term) => !tokenize(resumeText).includes(term)).slice(0, 6)
  const outdated = /designer/i.test(job.text)
  const row: MatchView = {
    jobId: job.id,
    resumeId,
    score,
    state: 'computed',
    breakdown: { keyword, semantic, weights: { keyword: weights.keyword, semantic: weights.semantic } },
    terms,
    explanation: explanationFor(score, terms, gaps),
    versions: outdated ? { ...CURRENT_VERSIONS, algorithm: 'weighted-legacy' } : CURRENT_VERSIONS,
    computedAt: now(),
    persisted: score >= threshold || persist,
    matchId: score >= threshold || persist ? `match-${job.id}` : undefined,
    evidence: job.text
      .split(/(?<=[.!?])\s+|\n+/)
      .map((part) => part.trim())
      .filter((part) => part.length >= 24)
      .slice(0, 5),
    highlights: terms.slice(0, 6),
    gaps,
    bucket:
      score >= 85
        ? { key: 'excellent', label: 'Excellent match', min: 85, score: Math.round(score) }
        : score >= 70
          ? { key: 'strong', label: 'Strong match', min: 70, score: Math.round(score) }
          : score >= 55
            ? { key: 'promising', label: 'Promising match', min: 55, score: Math.round(score) }
            : score >= 40
              ? { key: 'fair', label: 'Fair match', min: 40, score: Math.round(score) }
              : { key: 'poor', label: 'Poor match', min: 0, score: Math.round(score) },
  }
  if (row.persisted) {
    persisted[`${resumeId}:${job.id}`] = row
    const titleLine = (job.text.split('\n')[0] || job.id).replace(/^Title:\s*/i, '').trim()
    const companyLine = job.text.split('\n').find((line) => /^Company:/i.test(line))
    upsertMockReviewMatch({
      matchId: row.matchId || `match-${job.id}`,
      jobId: job.id,
      resumeId,
      jobTitle: titleLine || job.id,
      company: companyLine ? companyLine.replace(/^Company:\s*/i, '').trim() : 'Unknown',
      score,
      why: row.explanation,
      source: persist ? 'saved' : 'ai',
    })
  }
  return row
}

export const mockMatchingApi: MatchingApi = {
  async scoreMany(query) {
    await new Promise((resolve) => setTimeout(resolve, 40))
    return query.jobs.map((job) => scoreOne(query.resumeText, query.resumeId, job, query.threshold, query.persist === true))
  },
  async scoreOne(query) {
    await new Promise((resolve) => setTimeout(resolve, 40))
    return scoreOne(query.resumeText, query.resumeId, query.job, query.threshold, query.persist === true)
  },
  async listResults(query) {
    const wanted = query.jobIds ? new Set(query.jobIds) : null
    return Object.values(persisted)
      .filter((row) => row.resumeId === query.resumeId)
      .filter((row) => (wanted ? wanted.has(row.jobId) : true))
  },
  async warmup() {
    return { warm: true, elapsedMs: 1 }
  },
  async listRecords(query = {}) {
    return Object.values(persisted)
      .filter((row) => row.matchId && row.score != null)
      .filter((row) => (query.jobId ? row.jobId === query.jobId : true))
      .filter((row) => (query.resumeId ? row.resumeId === query.resumeId : true))
      .map((row) => ({
        id: row.matchId || `match-${row.jobId}`,
        jobId: row.jobId,
        resumeId: row.resumeId || '',
        modelVersion: row.versions?.algorithm || 'matching-v1',
        score: row.score || 0,
        createdAt: row.computedAt || now(),
        latest: true,
      }))
  },
  async getRecord(matchId) {
    const row = Object.values(persisted).find((item) => item.matchId === matchId)
    if (!row) throw new Error('match record not found')
    return {
      record: {
        id: matchId,
        jobId: row.jobId,
        resumeId: row.resumeId || '',
        modelVersion: row.versions?.algorithm || 'matching-v1',
        score: row.score || 0,
        createdAt: row.computedAt || now(),
        latest: true,
      },
      evidence: (row.evidence || []).map((sentence, index) => ({
        id: `${matchId}:${index}`,
        sentences: [sentence],
        createdAt: row.computedAt || now(),
      })),
    }
  },
  async rescore(matchId, score) {
    const detail = await mockMatchingApi.getRecord(matchId)
    const next = { ...detail.record, score: score ?? detail.record.score, updatedAt: now() }
    const key = Object.keys(persisted).find((item) => persisted[item].matchId === matchId)
    if (key && persisted[key].score != null) persisted[key] = { ...persisted[key], score: next.score }
    return { record: next }
  },
  async batchRescore(pairs) {
    const items = pairs.map((pair) => ({
      id: `match-${pair.jobId}`,
      jobId: pair.jobId,
      resumeId: pair.resumeId,
      score: pair.score,
      latest: true,
    }))
    return { count: items.length, items }
  },
}
