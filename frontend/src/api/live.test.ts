import { afterEach, describe, expect, it, vi } from 'vitest'
import { liveAutoApplyApi } from './autoApplyLive'
import { liveEmailApi } from './emailLive'
import { liveMatchingApi } from './matchingLive'
import { liveReviewApi } from './reviewLive'
import { ApiError, json, request } from './live'
import { DEFAULT_FILTERS } from '../lib/review'

function memoryStorage() {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubBrowser() {
  vi.stubGlobal('localStorage', memoryStorage())
  vi.stubGlobal('sessionStorage', memoryStorage())
  vi.stubGlobal('document', { cookie: '' })
}

describe('live request wrapper', () => {
  it('retries 503 GET then succeeds', async () => {
    stubBrowser()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('nope', { status: 503, headers: { 'Retry-After': '0' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const resp = await request('/api/v1/matches')
    expect(resp.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const body = await json<{ ok: boolean }>(resp)
    expect(body.ok).toBe(true)
  })

  it('maps API errors with retryable flag', async () => {
    stubBrowser()
    const resp = new Response(JSON.stringify({ error: { message: 'slow', code: 'RATE_LIMITED', retryable: true } }), {
      status: 429,
    })
    await expect(json(resp)).rejects.toMatchObject({ name: 'ApiError', status: 429, retryable: true })
    expect(new ApiError('x', 500, 'X', true).retryable).toBe(true)
  })

  it('typed domain clients hit contracted paths', async () => {
    stubBrowser()
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input)
      const jsonBody = (body: unknown) =>
        new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
      if (url.includes('/api/v1/matches?')) return jsonBody({ items: [] })
      if (url.includes('/api/v1/auto-apply/requests')) return jsonBody({ items: [] })
      if (url.includes('/api/v1/email/status')) return jsonBody({ connected: false })
      return jsonBody({})
    })
    vi.stubGlobal('fetch', fetchMock)
    await expect(liveReviewApi.list('matches', DEFAULT_FILTERS)).resolves.toEqual({ items: [], total: 0 })
    await expect(liveAutoApplyApi.list()).resolves.toEqual({ items: [] })
    await expect(liveEmailApi.status()).resolves.toEqual({ connected: false })
    await expect(
      liveMatchingApi.scoreMany({ resumeId: null, resumeText: '', jobs: [{ id: 'j1', text: 'eng' }], threshold: 70 }),
    ).resolves.toMatchObject([{ jobId: 'j1', state: 'no_resume' }])
    const called = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(called.some((url) => url.includes('/api/v1/matches?'))).toBe(true)
    expect(called.some((url) => url.includes('/api/v1/auto-apply/requests'))).toBe(true)
    expect(called.some((url) => url.includes('/api/v1/email/status'))).toBe(true)
  })
})
