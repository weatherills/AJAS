import { afterEach, describe, expect, it, vi } from 'vitest'
import { jobsListQueryString, liveJobsApi } from './jobsLive'

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

function jsonBody(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const emptyStatus = [
  {
    source: 'greenhouse',
    status: 'ok',
    lastSyncAt: null,
    backoffUntil: null,
    errorMessage: null,
    progress: null,
  },
  {
    source: 'lever',
    status: 'ok',
    lastSyncAt: null,
    backoffUntil: null,
    errorMessage: null,
    progress: null,
  },
]

describe('live jobs client', () => {
  it('encodes list query params including empty sources as none', () => {
    expect(
      jobsListQueryString({
        sources: [],
        q: 'staff',
        location: 'Austin',
        status: 'new',
        cursor: '25',
        limit: 25,
        since: '2026-09-01T00:00:00.000Z',
      }),
    ).toBe(
      'sources=none&q=staff&location=Austin&status=new&cursor=25&limit=25&since=2026-09-01T00%3A00%3A00.000Z',
    )
    expect(
      jobsListQueryString({
        sources: ['greenhouse', 'lever'],
        q: '',
        location: '',
        status: 'all',
        cursor: null,
        limit: 25,
      }),
    ).toBe('sources=greenhouse%2Clever&status=all&limit=25')
  })

  it('hits contracted job-source paths', async () => {
    stubBrowser()
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method || 'GET').toUpperCase()
      if (url.includes('/api/v1/jobs?')) return jsonBody({ items: [], nextCursor: null, total: 0 })
      if (url.includes('/api/v1/jobs/job-1')) return jsonBody({ id: 'job-1', title: 'Staff Engineer', sources: [] })
      if (url.includes('/api/v1/sources/status')) return jsonBody(emptyStatus)
      if (url.includes('/api/v1/sources/greenhouse/crawl') && method === 'POST') {
        return jsonBody({ run_id: 'run-1' }, 202)
      }
      if (url.includes('/api/v1/sources/lever/crawl') && method === 'POST') {
        return new Response(JSON.stringify({ error: { code: 'NOT_FOUND' } }), { status: 404 })
      }
      if (url.includes('/api/v1/sources/greenhouse/tenants/acme/crawl') && method === 'POST') {
        return jsonBody({ run_id: 'run-acme' }, 202)
      }
      if (url.includes('/api/v1/sources/greenhouse/tenants') && method === 'POST') {
        return jsonBody({ tenantKey: 'stripe', status: emptyStatus[0], sources: emptyStatus })
      }
      if (url.includes('/api/v1/sources/greenhouse/tenants/stripe') && method === 'DELETE') {
        return jsonBody({ tenantKey: 'stripe', deleted: true, status: emptyStatus[0], sources: emptyStatus })
      }
      return jsonBody({})
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      liveJobsApi.list({
        sources: ['greenhouse', 'lever'],
        q: '',
        location: '',
        status: 'all',
        cursor: null,
        limit: 25,
      }),
    ).resolves.toEqual({ items: [], nextCursor: null, total: 0 })
    await expect(liveJobsApi.get('job-1')).resolves.toMatchObject({ id: 'job-1' })
    await expect(liveJobsApi.sourceStatus()).resolves.toHaveLength(2)
    await expect(liveJobsApi.refresh('all')).resolves.toHaveLength(2)
    await expect(liveJobsApi.refreshTenant('greenhouse', 'acme')).resolves.toHaveLength(2)
    await expect(liveJobsApi.addTenant('greenhouse', { boardToken: 'stripe' })).resolves.toMatchObject({
      tenantKey: 'stripe',
    })
    await expect(liveJobsApi.removeTenant('greenhouse', 'stripe')).resolves.toMatchObject({ deleted: true })

    const called = fetchMock.mock.calls.map((call) => `${(call[1]?.method || 'GET').toString().toUpperCase()} ${String(call[0])}`)
    expect(called.some((row) => row.includes('GET /api/v1/jobs?'))).toBe(true)
    expect(called.some((row) => row.includes('GET /api/v1/jobs/job-1'))).toBe(true)
    expect(called.some((row) => row.includes('GET /api/v1/sources/status'))).toBe(true)
    expect(called.some((row) => row.includes('POST /api/v1/sources/greenhouse/crawl'))).toBe(true)
    expect(called.some((row) => row.includes('POST /api/v1/sources/lever/crawl'))).toBe(true)
    expect(called.some((row) => row.includes('POST /api/v1/sources/greenhouse/tenants/acme/crawl'))).toBe(true)
  })
})
