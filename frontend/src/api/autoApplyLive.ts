import { json, request } from './live'
import type { AutoApplyApi, ApplyDetail, ApplySummary, CreateApplyBody } from './autoApplyTypes'

export const liveAutoApplyApi: AutoApplyApi = {
  async create(body: CreateApplyBody) {
    return json(await request('/api/v1/auto-apply/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify(body),
    }))
  },
  async list(state) {
    const search = state ? `?state=${encodeURIComponent(state)}` : ''
    return json<{ items: ApplySummary[] }>(await request(`/api/v1/auto-apply/requests${search}`))
  },
  async get(requestId) {
    return json<ApplyDetail>(await request(`/api/v1/auto-apply/requests/${encodeURIComponent(requestId)}`))
  },
  async cancel(requestId) {
    return json(await request(`/api/v1/auto-apply/requests/${encodeURIComponent(requestId)}/cancel`, { method: 'POST' }))
  },
}
