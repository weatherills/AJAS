import type { LearningApi, LearningMetrics, LearningParams } from './learningTypes'

const DEFAULT_WEIGHTS = { keyword: 0.4, semantic: 0.6 }
const lastDecisions = new Map<string, string>()

const params: LearningParams = {
  weights: { ...DEFAULT_WEIGHTS },
  score_threshold: 0.7,
  model_version: 'learning-v1',
  source: 'global',
  status: 'active',
  tuningMode: 'auto',
  strictness: 1,
  updated_at: new Date().toISOString(),
  sample_size: 12,
}

function roundWeight(value: number) {
  return Math.round(value * 100) / 100
}

export function resetMockLearning() {
  params.weights = { ...DEFAULT_WEIGHTS }
  params.score_threshold = 0.7
  params.source = 'global'
  params.status = 'active'
  params.tuningMode = 'auto'
  params.strictness = 1
  params.sample_size = 12
  params.updated_at = new Date().toISOString()
  lastDecisions.clear()
}

export function mockLearningSnapshot() {
  return {
    weights: { ...params.weights },
    score_threshold: params.score_threshold,
    sample_size: params.sample_size,
    source: params.source,
  }
}

export function recordMockDecision(_matchId: string, decision: string) {
  params.source = 'personalized'
  params.updated_at = new Date().toISOString()
  if (decision === 'undo') {
    const prior = lastDecisions.get(_matchId)
    if (!prior) return
    params.sample_size = Math.max(0, params.sample_size - 1)
    if (prior === 'approve') {
      params.weights.keyword = roundWeight(Math.max(0.2, params.weights.keyword - 0.02))
    } else if (prior === 'reject') {
      params.weights.keyword = roundWeight(Math.min(0.7, params.weights.keyword + 0.02))
    }
    lastDecisions.delete(_matchId)
    params.weights.semantic = roundWeight(1 - params.weights.keyword)
    return
  }
  params.sample_size += 1
  if (decision === 'approve') {
    params.weights.keyword = roundWeight(Math.min(0.7, params.weights.keyword + 0.02))
  } else if (decision === 'reject') {
    params.weights.keyword = roundWeight(Math.max(0.2, params.weights.keyword - 0.02))
  }
  lastDecisions.set(_matchId, decision)
  params.weights.semantic = roundWeight(1 - params.weights.keyword)
}

export const mockLearningApi: LearningApi = {
  async params() {
    return { ...params, weights: { ...params.weights } }
  },
  async patchParams(body) {
    if (body.tuningMode) params.tuningMode = body.tuningMode
    if (body.strictness != null) {
      params.strictness = body.strictness
      params.score_threshold = [0.8, 0.7, 0.6][body.strictness] ?? 0.7
      params.source = 'personalized'
    }
    params.updated_at = new Date().toISOString()
    return mockLearningApi.params()
  },
  async metrics(period) {
    const row: LearningMetrics = {
      period,
      scope: 'self',
      approvals: 9,
      rejections: 3,
      skips: 0,
      decisions: 12,
      suggestions_shown: 10,
      precision_proxy: 0.75,
      recall_proxy: 0.8,
      at_k: { '3': 0.66, '10': 0.5 },
      threshold: params.score_threshold,
      model_version: params.model_version,
      approveRateDeltaPct: 8,
      liftVsBaseline: 25,
      empty: false,
      summary: `Last ${period}: 12 decisions, 75% approve rate, 10 matches shown above threshold.`,
    }
    return row
  },
  async validatePipeline(events) {
    return { accepted: events.length, rejected: 0, errors: [] }
  },
  async backfill(events) {
    return { applied: events.length }
  },
}
