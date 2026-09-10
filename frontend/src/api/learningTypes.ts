export type LearningParams = {
  weights: { keyword: number; semantic: number }
  score_threshold: number
  model_version: string
  source: 'global' | 'personalized'
  status: string
  tuningMode: 'auto' | 'manual'
  strictness: number
  updated_at: string
  sample_size: number
}

export type LearningMetrics = {
  period: '7d' | '30d'
  scope: string
  approvals: number
  rejections: number
  skips: number
  decisions: number
  suggestions_shown: number
  precision_proxy: number
  recall_proxy: number
  at_k: { '3': number; '10': number }
  threshold: number
  model_version: string
  approveRateDeltaPct: number | null
  empty: boolean
  summary: string
}

export type LearningApi = {
  params(): Promise<LearningParams>
  patchParams(body: { tuningMode?: 'auto' | 'manual'; strictness?: number }): Promise<LearningParams>
  metrics(period: '7d' | '30d'): Promise<LearningMetrics>
}
