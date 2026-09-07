import {
  combineScore,
  CURRENT_VERSIONS,
  explanationFor,
  keywordOverlap,
  matchedTerms,
  tokenize,
} from '../lib/matching'
import type { MatchingApi, MatchView } from './matchingTypes'

function now() {
  return new Date().toISOString()
}

function scoreOne(resumeText: string, resumeId: string | null, job: { id: string; text: string }, threshold: number): MatchView {
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
  const keyword = keywordOverlap(resumeText, job.text)
  const title = job.text.split('\n')[0] || job.text.slice(0, 80)
  const semantic = keywordOverlap(resumeText, `${title} ${title} ${job.text}`)
  const score = combineScore(keyword, semantic)
  const terms = matchedTerms(resumeText, job.text, 8)
  const gaps = tokenize(job.text).filter((term) => !tokenize(resumeText).includes(term)).slice(0, 6)
  const outdated = /designer/i.test(job.text)
  return {
    jobId: job.id,
    resumeId,
    score,
    state: 'computed',
    breakdown: { keyword, semantic, weights: { keyword: 0.4, semantic: 0.6 } },
    terms,
    explanation: explanationFor(score, terms, gaps),
    versions: outdated ? { ...CURRENT_VERSIONS, algorithm: 'weighted-legacy' } : CURRENT_VERSIONS,
    computedAt: now(),
    persisted: score >= threshold,
    matchId: score >= threshold ? `match-${job.id}` : undefined,
  }
}

export const mockMatchingApi: MatchingApi = {
  async scoreMany(query) {
    await new Promise((resolve) => setTimeout(resolve, 40))
    return query.jobs.map((job) => scoreOne(query.resumeText, query.resumeId, job, query.threshold))
  },
  async scoreOne(query) {
    await new Promise((resolve) => setTimeout(resolve, 40))
    return scoreOne(query.resumeText, query.resumeId, query.job, query.threshold)
  },
}
