const USER_KEY = 'ajas_user_id'
const CSRF_KEY = 'ajas_csrf'
const AAD_KEY = 'ajas_aad_token'

export function getUserId(): string {
  const existing = localStorage.getItem(USER_KEY)
  if (existing) return existing
  localStorage.setItem(USER_KEY, 'local-user')
  return 'local-user'
}

export function setUserId(id: string) {
  localStorage.setItem(USER_KEY, id.trim() || 'local-user')
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const parts = document.cookie.split(';')
  for (const part of parts) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return rest.join('=') || null
  }
  return null
}

export function getCsrfToken(): string | null {
  return sessionStorage.getItem(CSRF_KEY) || readCookie('ajas_csrf')
}

export function setCsrfToken(token: string | null | undefined) {
  if (token) sessionStorage.setItem(CSRF_KEY, token)
}

export function captureAadTokenFromHash() {
  if (typeof window === 'undefined') return
  const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash
  const params = new URLSearchParams(hash.includes('access_token=') ? hash : hash.split('?')[1] || '')
  const token = params.get('access_token')
  if (token) {
    sessionStorage.setItem(AAD_KEY, token)
    const cleaned = hash
      .split('&')
      .filter((part) => !part.startsWith('access_token=') && !part.startsWith('token_type=') && !part.startsWith('expires_in='))
      .join('&')
    if (cleaned && !cleaned.startsWith('/')) {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
    }
  }
}

export function authMode(): string {
  return (import.meta.env.VITE_AUTH_MODE || 'dev').toLowerCase()
}

function authorizationHeader(): string {
  if (authMode() === 'aad') {
    const jwt = sessionStorage.getItem(AAD_KEY)
    if (jwt) return `Bearer ${jwt}`
  }
  return `Bearer ${getUserId()}`
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  captureAadTokenFromHash()
  const headers = new Headers(init.headers)
  headers.set('Authorization', authorizationHeader())
  const csrf = getCsrfToken()
  if (csrf && !headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', csrf)
  const method = (init.method || 'GET').toUpperCase()
  if (method !== 'GET' && method !== 'HEAD' && !headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  const resp = await fetch(path, { ...init, headers, credentials: 'include' })
  const nextCsrf = resp.headers.get('X-CSRF-Token')
  if (nextCsrf) setCsrfToken(nextCsrf)
  return resp
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly retryable: boolean
  readonly retryAfter: number | null

  constructor(message: string, status: number, code: string | null = null, retryable = false, retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryable = retryable
    this.retryAfter = retryAfter
  }
}

export async function json<T>(resp: Response): Promise<T> {
  if (resp.status === 204) return undefined as T
  const body = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const message = body?.error?.message || `Request failed (${resp.status})`
    const retryAfterHeader = resp.headers.get('Retry-After')
    const retryAfter =
      body?.error?.details?.retryAfter ?? (retryAfterHeader ? Number(retryAfterHeader) : null)
    throw new ApiError(
      message,
      resp.status,
      body?.error?.code ?? null,
      Boolean(body?.error?.retryable) || resp.status === 429 || resp.status >= 500,
      Number.isFinite(retryAfter) ? Number(retryAfter) : null,
    )
  }
  if (body && typeof body === 'object' && 'csrfToken' in body && typeof body.csrfToken === 'string') {
    setCsrfToken(body.csrfToken)
  }
  return body as T
}

export type AuthConfig = {
  mode: string
  loginUrl: string | null
  configured: boolean
  oauthConfigured: boolean
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  try {
    return await json<AuthConfig>(await fetch('/api/v1/auth/config', { credentials: 'include' }))
  } catch {
    return { mode: authMode(), loginUrl: null, configured: authMode() !== 'aad', oauthConfigured: false }
  }
}
