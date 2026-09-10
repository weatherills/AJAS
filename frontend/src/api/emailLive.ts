import { json, request } from './live'
import type { EmailApi, EmailMessage, EmailStatus, EmailSuggestion, EmailTemplate, MessagePage, ThreadPage } from './emailTypes'

export const liveEmailApi: EmailApi = {
  async status() {
    return json<EmailStatus>(await request('/api/v1/email/status'))
  },
  async listThreads(query = {}) {
    const params = new URLSearchParams()
    if (query.jobId) params.set('jobId', query.jobId)
    if (query.unlinked) params.set('unlinked', 'true')
    params.set('limit', String(query.limit || 50))
    return json<ThreadPage>(await request(`/api/v1/email/threads?${params}`))
  },
  async listJobThreads(jobId) {
    return json<ThreadPage>(await request(`/api/v1/jobs/${encodeURIComponent(jobId)}/threads`))
  },
  async listMessages(threadId) {
    return json<MessagePage>(await request(`/api/v1/threads/${encodeURIComponent(threadId)}/messages`))
  },
  async reply(threadId, body) {
    return json<EmailMessage>(
      await request(`/api/v1/threads/${encodeURIComponent(threadId)}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async suggestions(threadId, body = {}) {
    const result = await json<{ items: EmailSuggestion[] }>(
      await request(`/api/v1/threads/${encodeURIComponent(threadId)}/suggestions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
    return result.items
  },
  async refresh() {
    return json<EmailStatus & { status: string }>(
      await request('/api/v1/email/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
    )
  },
  async templates() {
    const result = await json<{ items: EmailTemplate[] }>(await request('/api/v1/email/templates'))
    return result.items
  },
  async previewTemplate(id) {
    return json(await request(`/api/v1/email/templates/${encodeURIComponent(id)}/preview`))
  },
  async link(threadId, jobId) {
    return json(
      await request(`/api/v1/threads/${encodeURIComponent(threadId)}/link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId }),
      }),
    )
  },
  async unlink(threadId) {
    return json(
      await request(`/api/v1/threads/${encodeURIComponent(threadId)}/unlink`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      }),
    )
  },
}
