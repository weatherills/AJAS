import type { ResumeApi, ResumeListItem } from './types'

const USER_KEY = 'ajas_user_id'

export function getUserId(): string {
  const existing = localStorage.getItem(USER_KEY)
  if (existing) return existing
  localStorage.setItem(USER_KEY, 'local-user')
  return 'local-user'
}

export function setUserId(id: string) {
  localStorage.setItem(USER_KEY, id.trim() || 'local-user')
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${getUserId()}`)
  const resp = await fetch(path, { ...init, headers })
  return resp
}

async function json<T>(resp: Response): Promise<T> {
  if (resp.status === 204) return undefined as T
  const body = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const message = body?.error?.message || `Request failed (${resp.status})`
    throw new Error(message)
  }
  return body as T
}

export const liveApi: ResumeApi = {
  async list() {
    const data = await json<{ items: ResumeListItem[] }>(await request('/api/resumes?limit=100'))
    return data.items ?? []
  },
  async get(id) {
    return json(await request(`/api/resumes/${id}`))
  },
  async upload(file) {
    const form = new FormData()
    form.append('file', file)
    return json(await request('/api/resumes', { method: 'POST', body: form }))
  },
  async patch(id, body) {
    return json(
      await request(`/api/resumes/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async remove(id) {
    const resp = await request(`/api/resumes/${id}`, { method: 'DELETE' })
    if (!resp.ok && resp.status !== 204) {
      await json(resp)
    }
  },
  async previewUrl(id) {
    const data = await json<{ url: string }>(await request(`/api/resumes/${id}/preview-url`))
    return data.url
  },
  async retryParse(id) {
    await json(await request(`/api/resumes/${id}/retry-parse`, { method: 'POST' }))
  },
  async setActive(runId, resumeId) {
    return json(
      await request(`/api/runs/${runId}/active-resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resumeId }),
      }),
    )
  },
  async getActive(runId) {
    const resp = await request(`/api/runs/${runId}/active-resume`)
    if (resp.status === 404) return null
    return json(resp)
  },
}
