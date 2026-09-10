import { json, request } from './live'
import type { LearningApi, LearningMetrics, LearningParams } from './learningTypes'

export const liveLearningApi: LearningApi = {
  async params() {
    return json<LearningParams>(await request('/api/v1/learning/params'))
  },
  async patchParams(body) {
    return json<LearningParams>(
      await request('/api/v1/learning/params', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async metrics(period) {
    return json<LearningMetrics>(await request(`/api/v1/metrics?scope=self&period=${period}`))
  },
  async validatePipeline(events) {
    return json(await request('/api/v1/learning/pipeline/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
    }))
  },
  async backfill(events) {
    return json(await request('/api/v1/learning/pipeline/backfill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
    }))
  },
}
