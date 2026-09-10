import { describe, expect, it } from 'vitest'
import { mockJobsApi, resetMockJobs, simulateLeverRateLimit, simulateSourceError, simulateUnconfigured } from '../api/jobsMock'
import { mockSettingsApi, resetMockSettings, markMockSourceConfigured } from '../api/settingsMock'
import {
  alsoFromLabel,
  backoffRemainingMs,
  boardAddPayload,
  boardInputHint,
  canonicalKey,
  clearSessionFilters,
  defaultFilters,
  feedSourcesFromSettings,
  feedSourcesQueryParam,
  formatCountdown,
  mergeJobs,
  matchesQuery,
  nextFeedSources,
  paginate,
  PAGE_SIZE,
  persistFeedSourceChip,
  refreshToastForStatuses,
  sourceChipPatch,
  sourceErrorCopy,
  addBoardToast,
  boardErrorCopy,
  feedErrorLines,
  sourceBoardErrors,
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

  it('builds a Settings PATCH from a Job Feed chip and leaves session filters when clearing search', () => {
    expect(sourceChipPatch('greenhouse', false)).toEqual({ sources: { greenhouseEnabled: false } })
    expect(sourceChipPatch('lever', true)).toEqual({ sources: { leverEnabled: true } })
    expect(nextFeedSources(['greenhouse', 'lever'], 'lever')).toEqual({ sources: ['greenhouse'], enabled: false })
    expect(nextFeedSources(['greenhouse'], 'lever')).toEqual({ sources: ['greenhouse', 'lever'], enabled: true })
    expect(nextFeedSources(['greenhouse'], 'greenhouse')).toEqual({ sources: [], enabled: false })
    const cleared = clearSessionFilters({
      sources: [],
      q: 'staff',
      location: 'Austin',
      status: 'new',
      pagination: 'pages',
    })
    expect(cleared.sources).toEqual([])
    expect(cleared.q).toBe('')
    expect(cleared.location).toBe('')
    expect(cleared.status).toBe('all')
    expect(cleared.pagination).toBe('infinite')
    expect(feedSourcesQueryParam([])).toBe('none')
    expect(feedSourcesQueryParam(['greenhouse'])).toBe('greenhouse')
    expect(feedSourcesQueryParam(['greenhouse', 'lever'])).toBe('greenhouse,lever')
  })

  it('persists Job Feed chips through Settings so both-off survives a reload', async () => {
    resetMockSettings()
    const first = await mockSettingsApi.get()
    expect(feedSourcesFromSettings(first.sources)).toEqual(['greenhouse', 'lever'])
    expect(await persistFeedSourceChip(mockSettingsApi, 'greenhouse', false)).toEqual(['lever'])
    expect(await persistFeedSourceChip(mockSettingsApi, 'lever', false)).toEqual([])
    const reloaded = await mockSettingsApi.get()
    expect(reloaded.sources.greenhouseEnabled).toBe(false)
    expect(reloaded.sources.leverEnabled).toBe(false)
    expect(feedSourcesFromSettings(reloaded.sources)).toEqual([])
    markMockSourceConfigured('greenhouse', true)
    markMockSourceConfigured('lever', true)
    const stillOff = await mockSettingsApi.get()
    expect(feedSourcesFromSettings(stillOff.sources)).toEqual([])
    expect(await persistFeedSourceChip(mockSettingsApi, 'greenhouse', true)).toEqual(['greenhouse'])
  })

  it('keeps SOURCE_NOT_CONFIGURED when a Job Feed chip turns on a source with zero tenants', async () => {
    resetMockSettings()
    markMockSourceConfigured('greenhouse', false)
    await expect(persistFeedSourceChip(mockSettingsApi, 'greenhouse', true)).rejects.toMatchObject({
      code: 'SOURCE_NOT_CONFIGURED',
    })
    const doc = await mockSettingsApi.get()
    expect(doc.sources.greenhouseEnabled).toBe(false)
    expect(doc.sources.greenhouseConfigured).toBe(false)
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

  it('returns no jobs when the sources query is empty', async () => {
    resetMockJobs()
    const page = await mockJobsApi.list({
      sources: [],
      q: '',
      location: '',
      status: 'all',
      cursor: null,
      limit: 25,
    })
    expect(page.items).toEqual([])
    expect(page.total).toBe(0)
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
    const named = greenhouse?.boards?.find((item) => item.tenantKey === 'acme')
    expect(boardErrorCopy(named!, greenhouse!, greenhouse?.boards?.length || 1)).toMatch(/not found/i)
    expect(feedErrorLines(after).some((item) => /not found/i.test(item.message))).toBe(true)
    expect(
      boardErrorCopy(
        { tenantKey: 'keep-board', enabled: true, status: 'ok', errorMessage: null },
        greenhouse!,
        2,
      ),
    ).toBeNull()
    expect(
      boardErrorCopy(
        { tenantKey: 'no-such-board', enabled: true, status: 'ok', errorMessage: null },
        greenhouse!,
        2,
      ),
    ).toMatch(/no-such-board/)
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

  it('stamps a missing-board crawl error on that Settings board row', async () => {
    resetMockJobs()
    simulateUnconfigured('greenhouse')
    const created = await mockJobsApi.addTenant('greenhouse', { boardToken: 'no-such-board' })
    const row = created.status
    expect(row?.configured).toBe(true)
    expect(row?.status).toBe('error')
    const board = row?.boards?.find((item) => item.tenantKey === 'no-such-board')
    expect(boardErrorCopy(board!, row!, row?.boards?.length || 1)).toMatch(/not found/i)
    expect(boardErrorCopy(board!, row!, row?.boards?.length || 1)).toMatch(/no-such-board/)
    await mockJobsApi.addTenant('greenhouse', { boardToken: 'keep-board' })
    const after = await mockJobsApi.sourceStatus()
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    const bad = greenhouse?.boards?.find((item) => item.tenantKey === 'no-such-board')
    const good = greenhouse?.boards?.find((item) => item.tenantKey === 'keep-board')
    expect(boardErrorCopy(bad!, greenhouse!, greenhouse?.boards?.length || 2)).toMatch(/no-such-board/)
    expect(boardErrorCopy(good!, greenhouse!, greenhouse?.boards?.length || 2)).toBeNull()
  })

  it('lists every failed board instead of collapsing to the last tenant', async () => {
    resetMockJobs()
    simulateUnconfigured('greenhouse')
    const first = await mockJobsApi.addTenant('greenhouse', { boardToken: 'no-such-board' })
    expect(addBoardToast('greenhouse', first).tone).toBe('error')
    expect(addBoardToast('greenhouse', first).text).toMatch(/no-such-board/)
    await mockJobsApi.addTenant('greenhouse', { boardToken: 'missing-board' })
    const after = await mockJobsApi.sourceStatus()
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    expect(sourceBoardErrors(greenhouse!).map((item) => item.tenantKey).sort()).toEqual(['missing-board', 'no-such-board'])
    const lines = feedErrorLines(after)
    expect(lines.some((item) => /no-such-board/.test(item.message))).toBe(true)
    expect(lines.some((item) => /missing-board/.test(item.message))).toBe(true)
    const toast = refreshToastForStatuses('all', after, 0)
    expect(toast.tone).toBe('error')
    expect(toast.text).toMatch(/no-such-board/)
    expect(toast.text).toMatch(/missing-board/)
  })

  it('toasts a successful board add and retries one tenant without clearing the other', async () => {
    resetMockJobs()
    simulateUnconfigured('greenhouse')
    const created = await mockJobsApi.addTenant('greenhouse', { boardToken: 'stripe' })
    expect(addBoardToast('greenhouse', created)).toEqual({
      text: 'Greenhouse board “stripe” added',
      tone: 'info',
    })
    await mockJobsApi.addTenant('greenhouse', { boardToken: 'no-such-board' })
    const retried = await mockJobsApi.refreshTenant('greenhouse', 'no-such-board')
    const greenhouse = retried.find((item) => item.source === 'greenhouse')
    const bad = greenhouse?.boards?.find((item) => item.tenantKey === 'no-such-board')
    const good = greenhouse?.boards?.find((item) => item.tenantKey === 'stripe')
    expect(boardErrorCopy(bad!, greenhouse!, greenhouse?.boards?.length || 2)).toMatch(/no-such-board/)
    expect(boardErrorCopy(good!, greenhouse!, greenhouse?.boards?.length || 2)).toBeNull()
    await expect(mockJobsApi.refreshTenant('greenhouse', 'not-on-file')).rejects.toMatchObject({ code: 'NOT_FOUND' })
  })

  it('removes a board and flips the last tenant back to unconfigured', async () => {
    resetMockJobs()
    resetMockSettings()
    simulateUnconfigured('greenhouse')
    await mockJobsApi.addTenant('greenhouse', { boardToken: 'no-such-board' })
    await mockJobsApi.addTenant('greenhouse', { boardToken: 'keep-board' })
    const dropped = await mockJobsApi.removeTenant('greenhouse', 'no-such-board')
    expect(dropped.deleted).toBe(true)
    expect(dropped.status?.configured).toBe(true)
    expect(dropped.status?.boards?.map((item) => item.tenantKey)).toEqual(['keep-board'])
    const last = await mockJobsApi.removeTenant('greenhouse', 'keep-board')
    expect(last.status?.configured).toBe(false)
    expect(last.status?.status).toBe('unconfigured')
    expect(last.status?.boards).toEqual([])
    const after = await mockJobsApi.sourceStatus()
    const greenhouse = after.find((item) => item.source === 'greenhouse')
    expect(sourceIsConfiguredStatus(greenhouse)).toBe(false)
    expect(statusLabel(greenhouse!)).toBe('Not configured')
    const settings = await mockSettingsApi.get()
    expect(settings.sources.greenhouseConfigured).toBe(false)
    expect(settings.sources.greenhouseEnabled).toBe(false)
    await expect(persistFeedSourceChip(mockSettingsApi, 'greenhouse', true)).rejects.toMatchObject({
      code: 'SOURCE_NOT_CONFIGURED',
    })
  })
})
