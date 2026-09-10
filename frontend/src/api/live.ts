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

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${getUserId()}`)
  return fetch(path, { ...init, headers })
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null

  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function json<T>(resp: Response): Promise<T> {
  if (resp.status === 204) return undefined as T
  const body = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const message = body?.error?.message || `Request failed (${resp.status})`
    throw new ApiError(message, resp.status, body?.error?.code ?? null)
  }
  return body as T
}
