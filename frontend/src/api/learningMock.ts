import type { LearningApi, LearningMetrics, LearningParams } from './learningTypes'

const params: LearningParams = {
  weights: { keyword: 0.4, semantic: 0.6 },
  score_threshold: 0.7,
  model_version: 'learning-v1',
  source: 'global',
  status: 'active',
  tuningMode: 'auto',
  strictness: 1,
  updated_at: new Date().toISOString(),
  sample_size: 12,
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
      empty: false,
      summary: `Last ${period}: 12 decisions, 75% approve rate, 10 matches shown above threshold.`,
    }
    return row
  },
}
