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
  async markManualSubmitted(requestId) {
    return json(
      await request(`/api/v1/auto-apply/requests/${encodeURIComponent(requestId)}/manual-submit`, { method: 'POST' }),
    )
  },
  async extractCoverLetter(file) {
    const form = new FormData()
    form.append('file', file)
    const data = await json<{ text: string }>(
      await request('/api/v1/auto-apply/cover-letter/extract', { method: 'POST', body: form }),
    )
    return data.text
  },
  async previewCoverLetter(body) {
    const data = await json<{ text: string; source?: string }>(
      await request('/api/v1/auto-apply/cover-letter/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
    return { text: data.text, source: data.source || 'ai' }
  },
}
