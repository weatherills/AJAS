import { describe, expect, it } from 'vitest'
import { mockJobsApi, resetMockJobs, simulateLeverRateLimit, simulateSourceError, simulateUnconfigured } from '../api/jobsMock'
import {
  alsoFromLabel,
  backoffRemainingMs,
  boardAddPayload,
  boardInputHint,
  canonicalKey,
  defaultFilters,
  feedSourcesFromSettings,
  formatCountdown,
  mergeJobs,
  matchesQuery,
  paginate,
  PAGE_SIZE,
  refreshToastForStatuses,
  sourceErrorCopy,
  sourceIsConfiguredStatus,
  sourceUnconfiguredCopy,
  sourcesOffCopy,
  statusLabel,
} from './jobs'
import type { JobCard } from '../api/jobsTypes'

function sample(id: string, source: 'greenhouse' | 'lever', key = 'staff-engineer|remote|acme'): JobCard {
  return {
    id,
    canonicalKey: key,
    title: 'Staff Engineer',
    company: 'Acme',
    location: 'Remote',
    employmentType: 'Full-time',
    snippet: 'Build crawlers.',
    applyUrl: `https://example.com/${id}`,
    updatedAt: '2026-09-07T12:00:00.000Z',
    isNew: false,
    primarySource: source,
    sources: [
      {
        source,
        sourceUrl: `https://example.com/${id}`,
        postedAt: '2026-09-07T12:00:00.000Z',
        domain: 'example.com',
      },
    ],
  }
}

describe('job feed helpers', () => {
  it('builds a stable canonical key', () => {
    expect(canonicalKey(' Staff Engineer ', 'Remote', 'Acme')).toBe('staff-engineer|remote|acme')
  })

  it('merges Greenhouse and Lever rows that share a canonical key', () => {
    const merged = mergeJobs([sample('gh', 'greenhouse'), sample('lv', 'lever')])
    expect(merged).toHaveLength(1)
    expect(merged[0].sources.map((item) => item.source).sort()).toEqual(['greenhouse', 'lever'])
    expect(alsoFromLabel(merged[0].sources, 'greenhouse')).toBe('Also found on Lever')
  })

  it('filters by source, query, location, and new status', () => {
    const job = { ...sample('gh', 'greenhouse'), isNew: true, location: 'Austin, TX' }
    expect(matchesQuery(job, { sources: ['greenhouse'], q: 'staff', location: 'austin', status: 'new', cursor: null, limit: 25 })).toBe(
      true,
    )
    expect(matchesQuery(job, { sources: ['lever'], q: '', location: '', status: 'all', cursor: null, limit: 25 })).toBe(false)
    expect(matchesQuery(job, { sources: ['greenhouse'], q: '', location: '', status: 'all', cursor: null, limit: 25 })).toBe(true)
    expect(matchesQuery(job, { sources: [], q: '', location: '', status: 'all', cursor: null, limit: 25 })).toBe(false)
  })

  it('paginates 25 items and stops at the end', () => {
    const items = Array.from({ length: 40 }, (_, index) => index)
    const first = paginate(items, null, PAGE_SIZE)
    expect(first.items).toHaveLength(25)
    expect(first.nextCursor).toBe('25')
    const second = paginate(items, first.nextCursor, PAGE_SIZE)
    expect(second.items).toHaveLength(15)
    expect(second.nextCursor).toBeNull()
  })

  it('formats backoff countdown as mm:ss', () => {
    expect(formatCountdown(125_000)).toBe('02:05')
    expect(backoffRemainingMs(new Date(Date.now() + 4_000).toISOString(), Date.now())).toBeGreaterThan(0)
    expect(defaultFilters().sources).toEqual(['greenhouse', 'lever'])
  })

  it('maps Settings source flags onto Job Feed filters without treating a missing configured flag as off', () => {
    expect(feedSourcesFromSettings({ greenhouseEnabled: true, leverEnabled: true, greenhouseConfigured: true, leverConfigured: true })).toEqual(
      ['greenhouse', 'lever'],
    )
    expect(feedSourcesFromSettings({ greenhouseEnabled: false, leverEnabled: false, greenhouseConfigured: true, leverConfigured: true })).toEqual([])
    expect(feedSourcesFromSettings({ greenhouseEnabled: true, leverEnabled: false, greenhouseConfigured: true, leverConfigured: false })).toEqual([
      'greenhouse',
    ])
    expect(feedSourcesFromSettings({ greenhouseEnabled: false, leverEnabled: false })).toBeNull()
  })
})

describe('mock jobs api', () => {
  it('returns a deduped first page and a merged Acme Staff Engineer', async () => {
    resetMockJobs()
    const page = await mockJobsApi.list({
      sources: ['greenhouse', 'lever'],
      q: '',
      location: '',
      status: 'all',
      cursor: null,
      limit: 25,
    })
    expect(page.items.length).toBe(25)
    expect(page.nextCursor).toBeTruthy()
    const staff = page.items.find((item) => item.title === 'Staff Engineer' && item.company === 'Acme')
    expect(staff?.sources.length).toBe(2)
  })

  it('returns the Acme Staff Engineer by the id Review and Email mocks share', async () => {
    resetMockJobs()
    const staff = await mockJobsApi.get('job-1')
    expect(staff.title).toBe('Staff Engineer')
    expect(staff.company).toBe('Acme')
  })

  it('skips Lever refresh while rate-limited', async () => {
    resetMockJobs()
    simulateLeverRateLimit(30)
    const before = await mockJobsApi.sourceStatus()
    expect(before.find((item) => item.source === 'lever')?.status).toBe('rate_limited')
    const after = await mockJobsApi.refresh('all')
    expect(after.find((item) => item.source === 'lever')?.status).toBe('rate_limited')
    expect(after.find((item) => item.source === 'greenhouse')?.status).toBe('ok')
  })

  it('keeps a durable source error instead of clearing it on refresh', async () => {
    resetMockJobs()
    simulateSourceError('greenhouse', 'Greenhouse board "no-such-board" was not found. Check the board token or URL.')
    const after = await mockJobsApi.refresh('all')
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    expect(greenhouse?.status).toBe('error')
    expect(greenhouse?.errorMessage).toMatch(/not found/i)
    expect(sourceErrorCopy(greenhouse!)).toMatch(/not found/i)
    expect(sourceErrorCopy({ source: 'lever', status: 'ok', errorMessage: null })).toBeNull()
    expect(statusLabel(greenhouse!)).toBe('Board not found')
    const toast = refreshToastForStatuses('all', after, 0)
    expect(toast.tone).toBe('error')
    expect(toast.text).toMatch(/not found/i)
  })

  it('keeps an unconfigured source from looking like a successful refresh', async () => {
    resetMockJobs()
    simulateUnconfigured('greenhouse')
    const after = await mockJobsApi.refresh('all')
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    expect(greenhouse?.status).toBe('unconfigured')
    expect(greenhouse?.configured).toBe(false)
    expect(sourceIsConfiguredStatus(greenhouse)).toBe(false)
    expect(statusLabel(greenhouse!)).toBe('Not configured')
    expect(sourceUnconfiguredCopy(greenhouse!)).toMatch(/board token/i)
    expect(sourceErrorCopy(greenhouse!)).toBeNull()
    const toast = refreshToastForStatuses('greenhouse', after, 0)
    expect(toast.tone).toBe('error')
    expect(toast.text).toMatch(/not configured/i)
    expect(toast.live).toBe('Source not configured')
  })

  it('adds a board token and flips an unconfigured source on', async () => {
    resetMockJobs()
    simulateUnconfigured('greenhouse')
    const created = await mockJobsApi.addTenant('greenhouse', { boardToken: 'stripe' })
    expect(created.tenantKey).toBe('stripe')
    expect(created.status?.configured).toBe(true)
    expect(created.status?.status).not.toBe('unconfigured')
    const after = await mockJobsApi.sourceStatus()
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    expect(sourceIsConfiguredStatus(greenhouse)).toBe(true)
    expect(greenhouse?.boards?.some((item) => item.tenantKey === 'stripe')).toBe(true)
    expect(boardAddPayload('https://jobs.lever.co/openai')).toEqual({ boardUrl: 'https://jobs.lever.co/openai' })
    expect(boardAddPayload('acme')).toEqual({ boardToken: 'acme' })
    expect(boardInputHint('greenhouse')).toMatch(/boards.greenhouse.io/i)
    expect(sourcesOffCopy()).toMatch(/turned off in Settings/i)
  })
})
