import type { AddTenantResult, JobCard, JobListQuery, JobSourceName, JobsApi, SourceBoard, SourceStatus } from './jobsTypes'
import { boardAddPayload, canonicalKey, mergeJobs, matchesQuery, paginate, PAGE_SIZE, sourceDomain } from '../lib/jobs'
import { markMockSourceConfigured } from './settingsMock'

type RawJob = Omit<JobCard, 'isNew' | 'snippet'> & {
  description: string
  createdAt: string
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3600_000).toISOString()
}

function card(job: RawJob, since: string | null): JobCard {
  return {
    id: job.id,
    canonicalKey: job.canonicalKey || canonicalKey(job.title, job.location, job.company),
    title: job.title,
    company: job.company,
    location: job.location,
    employmentType: job.employmentType,
    snippet: job.description.slice(0, 160),
    applyUrl: job.applyUrl,
    updatedAt: job.updatedAt,
    isNew: Boolean(since && job.updatedAt > since),
    sources: job.sources,
    primarySource: job.primarySource,
  }
}

function seedJobs(): RawJob[] {
  const titles = [
    'Staff Engineer',
    'Platform Engineer',
    'Frontend Engineer',
    'Backend Engineer',
    'Data Engineer',
    'Security Engineer',
    'Product Designer',
    'Engineering Manager',
  ]
  const companies = ['Acme', 'Globex', 'Initech', 'Umbrella', 'Hooli']
  const locations = ['Remote', 'Austin, TX', 'New York, NY', 'London']
  const jobs: RawJob[] = []
  let index = 1
  for (const company of companies) {
    for (const title of titles) {
      const location = locations[index % locations.length]
      const source: JobSourceName = index % 2 === 0 ? 'lever' : 'greenhouse'
      const id = `job-${index}`
      const url =
        source === 'greenhouse'
          ? `https://boards.greenhouse.io/${company.toLowerCase()}/jobs/${index}`
          : `https://jobs.lever.co/${company.toLowerCase()}/${id}`
      jobs.push({
        id,
        canonicalKey: canonicalKey(title, location, company),
        title,
        company,
        location,
        employmentType: 'Full-time',
        applyUrl: url,
        updatedAt: hoursAgo(index),
        createdAt: hoursAgo(index + 24),
        primarySource: source,
        sources: [{ source, sourceUrl: url, postedAt: hoursAgo(index), domain: sourceDomain(url) }],
        description: `${title} at ${company} in ${location}. Build public job ingestion, matching, and review tools for AJAS.`,
      })
      index += 1
    }
  }
  const twin = jobs.find((item) => item.title === 'Staff Engineer' && item.company === 'Acme')
  if (twin) {
    jobs.push({
      ...twin,
      id: 'job-lever-acme-staff',
      primarySource: 'lever',
      updatedAt: hoursAgo(0.5),
      sources: [
        {
          source: 'lever',
          sourceUrl: 'https://jobs.lever.co/acme/staff-engineer',
          postedAt: hoursAgo(0.5),
          domain: 'jobs.lever.co',
        },
      ],
    })
  }
  return jobs
}

let jobs = seedJobs()
let statuses: SourceStatus[] = [
  {
    source: 'greenhouse',
    status: 'ok',
    lastSyncAt: hoursAgo(1),
    backoffUntil: null,
    errorMessage: null,
    progress: null,
    configured: true,
    tenantCount: 1,
    boards: [{ tenantKey: 'acme', enabled: true, status: 'ok', errorMessage: null }],
  },
  {
    source: 'lever',
    status: 'ok',
    lastSyncAt: hoursAgo(2),
    backoffUntil: null,
    errorMessage: null,
    progress: null,
    configured: true,
    tenantCount: 1,
    boards: [{ tenantKey: 'acme', enabled: true, status: 'ok', errorMessage: null }],
  },
]
let extraAdded = false

export function resetMockJobs() {
  jobs = seedJobs()
  extraAdded = false
  statuses = [
    {
      source: 'greenhouse',
      status: 'ok',
      lastSyncAt: hoursAgo(1),
      backoffUntil: null,
      errorMessage: null,
      progress: null,
      configured: true,
      tenantCount: 1,
      boards: [{ tenantKey: 'acme', enabled: true, status: 'ok', errorMessage: null }],
    },
    {
      source: 'lever',
      status: 'ok',
      lastSyncAt: hoursAgo(2),
      backoffUntil: null,
      errorMessage: null,
      progress: null,
      configured: true,
      tenantCount: 1,
      boards: [{ tenantKey: 'acme', enabled: true, status: 'ok', errorMessage: null }],
    },
  ]
}

export function simulateUnconfigured(source: JobSourceName) {
  statuses = statuses.map((item) =>
    item.source === source
      ? {
          ...item,
          status: 'unconfigured',
          lastSyncAt: null,
          backoffUntil: null,
          errorMessage: `${source === 'greenhouse' ? 'Greenhouse' : 'Lever'} is not configured. Add a board token before turning this source on, or Job Feed stays empty.`,
          progress: null,
          configured: false,
          tenantCount: 0,
          boards: [],
        }
      : item,
  )
}

export function simulateSourceError(source: JobSourceName, message: string) {
  statuses = statuses.map((item) => {
    if (item.source !== source) return item
    const boards = stampBoardError(item.boards || [], message)
    return {
      ...item,
      status: 'error',
      backoffUntil: null,
      errorMessage: message,
      progress: null,
      boards,
    }
  })
}

function mockListingError(source: JobSourceName, key: string): string | null {
  if (!/no-such|not-found|missing|404/i.test(key)) return null
  const name = source === 'greenhouse' ? 'Greenhouse' : 'Lever'
  return `${name} board "${key}" was not found. Check the board token or URL.`
}

function stampBoardError(boards: SourceBoard[], message: string): SourceBoard[] {
  const lowered = message.toLowerCase()
  const named = boards.map((board) =>
    lowered.includes(board.tenantKey.toLowerCase())
      ? { ...board, status: 'error' as const, errorMessage: message }
      : board,
  )
  if (named.some((board) => board.status === 'error' && board.errorMessage)) return named
  if (boards.length === 1) {
    return [{ ...boards[0], status: 'error', errorMessage: message }]
  }
  return named
}

function syncSourceFromBoards(row: SourceStatus): SourceStatus {
  const boards = row.boards || []
  if (boards.length === 0) {
    return {
      ...row,
      configured: false,
      status: 'unconfigured',
      lastSyncAt: null,
      backoffUntil: null,
      errorMessage: `${row.source === 'greenhouse' ? 'Greenhouse' : 'Lever'} is not configured. Add a board token before turning this source on, or Job Feed stays empty.`,
      progress: null,
      tenantCount: 0,
    }
  }
  const failed = boards.find((board) => board.status === 'error' && board.errorMessage)
  if (failed) {
    return {
      ...row,
      configured: true,
      tenantCount: boards.length,
      status: 'error',
      errorMessage: failed.errorMessage || row.errorMessage,
    }
  }
  const clearError = row.status === 'error' || row.status === 'unconfigured'
  return {
    ...row,
    configured: true,
    tenantCount: boards.length,
    status: clearError ? 'ok' : row.status,
    errorMessage: clearError ? null : row.errorMessage,
  }
}

export function simulateLeverRateLimit(seconds = 12) {
  const until = new Date(Date.now() + seconds * 1000).toISOString()
  statuses = statuses.map((item) =>
    item.source === 'lever'
      ? {
          ...item,
          status: 'rate_limited',
          backoffUntil: until,
          errorMessage: 'Provider returned HTTP 429',
          progress: null,
        }
      : item,
  )
}

function currentStatuses(now = Date.now()): SourceStatus[] {
  return statuses.map((item) => {
    if (item.status === 'rate_limited' && item.backoffUntil && new Date(item.backoffUntil).getTime() <= now) {
      return { ...item, status: 'ok', backoffUntil: null, errorMessage: null }
    }
    return item
  })
}

function filteredCards(query: JobListQuery): JobCard[] {
  const merged = mergeJobs(jobs.map((item) => card(item, query.since ?? null)))
  return merged.filter((item) => matchesQuery(item, query))
}

export const mockJobsApi: JobsApi = {
  async list(query) {
    const all = filteredCards(query)
    const page = paginate(all, query.cursor, query.limit || PAGE_SIZE)
    return { items: page.items, nextCursor: page.nextCursor, total: all.length }
  },
  async get(id) {
    const merged = mergeJobs(jobs.map((item) => card(item, null)))
    const found = merged.find((item) => item.id === id)
    const raw = jobs.find((item) => item.id === id) || jobs.find((item) => item.canonicalKey === found?.canonicalKey)
    if (!found || !raw) throw new Error('Job not found')
    return { ...found, description: raw.description, descriptionError: null }
  },
  async sourceStatus() {
    statuses = currentStatuses()
    return structuredClone(statuses)
  },
  async refresh(source) {
    statuses = currentStatuses()
    const targets: JobSourceName[] = source === 'all' ? ['greenhouse', 'lever'] : [source]
    for (const name of targets) {
      const row = statuses.find((item) => item.source === name)
      if (!row) continue
      if (row.status === 'error' || row.status === 'unconfigured' || row.configured === false) continue
      if (row.status === 'rate_limited' && row.backoffUntil && new Date(row.backoffUntil).getTime() > Date.now()) {
        continue
      }
      row.status = 'syncing'
      row.progress = name === 'greenhouse' ? 'page 1/2' : null
      row.errorMessage = null
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
    for (const name of targets) {
      const row = statuses.find((item) => item.source === name)
      if (!row || row.status === 'rate_limited') continue
      if (name === 'greenhouse' && !extraAdded) {
        extraAdded = true
        jobs.unshift({
          id: 'job-new-greenhouse',
          canonicalKey: canonicalKey('Applied Scientist', 'Remote', 'Acme'),
          title: 'Applied Scientist',
          company: 'Acme',
          location: 'Remote',
          employmentType: 'Full-time',
          applyUrl: 'https://boards.greenhouse.io/acme/jobs/new',
          updatedAt: new Date().toISOString(),
          createdAt: new Date().toISOString(),
          primarySource: 'greenhouse',
          sources: [
            {
              source: 'greenhouse',
              sourceUrl: 'https://boards.greenhouse.io/acme/jobs/new',
              postedAt: new Date().toISOString(),
              domain: 'boards.greenhouse.io',
            },
          ],
          description: 'New Greenhouse posting after a manual refresh.',
        })
      }
      if (row.status === 'error' || row.status === 'unconfigured' || row.configured === false) continue
      row.status = 'ok'
      row.lastSyncAt = new Date().toISOString()
      row.progress = null
    }
    return structuredClone(statuses)
  },
  async refreshTenant(source, tenantKey) {
    statuses = currentStatuses()
    const row = statuses.find((item) => item.source === source)
    if (!row) throw Object.assign(new Error('not found'), { code: 'NOT_FOUND' })
    const boards = [...(row.boards || [])]
    const index = boards.findIndex((item) => item.tenantKey === tenantKey)
    if (index < 0) throw Object.assign(new Error('not found'), { code: 'NOT_FOUND' })
    const listingError = mockListingError(source, tenantKey)
    boards[index] = {
      ...boards[index],
      status: listingError ? 'error' : 'ok',
      errorMessage: listingError,
      lastSyncAt: new Date().toISOString(),
    }
    row.boards = boards
    Object.assign(row, syncSourceFromBoards(row))
    if (!listingError) {
      row.lastSyncAt = boards[index].lastSyncAt || row.lastSyncAt
      row.progress = null
    }
    return structuredClone(statuses)
  },
  async addTenant(source, body) {
    const raw = (body.boardToken || body.boardUrl || '').trim()
    if (!raw) throw Object.assign(new Error('board token or URL is required'), { code: 'VALIDATION_ERROR' })
    const payload = boardAddPayload(raw)
    const key = (payload.boardToken || payload.boardUrl || raw)
      .replace(/^https:\/\/(boards\.greenhouse\.io|boards-api\.greenhouse\.io\/v1\/boards|jobs\.lever\.co|api\.lever\.co\/v0\/postings)\//i, '')
      .split(/[/?#]/)[0]
      .toLowerCase()
    if (!key) throw Object.assign(new Error('board token or URL is required'), { code: 'VALIDATION_ERROR' })
    statuses = currentStatuses()
    const row = statuses.find((item) => item.source === source)
    if (row) {
      const boards = [...(row.boards || [])]
      const listingError = mockListingError(source, key)
      if (!boards.some((item) => item.tenantKey === key)) {
        boards.push({
          tenantKey: key,
          enabled: body.enabled !== false,
          status: listingError ? 'error' : 'ok',
          errorMessage: listingError,
        })
      }
      row.boards = boards
      Object.assign(row, syncSourceFromBoards(row))
    }
    markMockSourceConfigured(source, true)
    const sources = structuredClone(statuses)
    const result: AddTenantResult = {
      id: `tenant-${source}-${key}`,
      sourceId: source,
      tenantKey: key,
      enabled: body.enabled !== false,
      status: structuredClone(row || null),
      sources,
    }
    return result
  },
  async removeTenant(source, tenantKey) {
    const key = tenantKey.trim()
    statuses = currentStatuses()
    const row = statuses.find((item) => item.source === source)
    if (!row) throw Object.assign(new Error('not found'), { code: 'NOT_FOUND' })
    const boards = (row.boards || []).filter((item) => item.tenantKey !== key)
    if (boards.length === (row.boards || []).length) {
      throw Object.assign(new Error('not found'), { code: 'NOT_FOUND' })
    }
    row.boards = boards
    Object.assign(row, syncSourceFromBoards(row))
    if (boards.length === 0) {
      markMockSourceConfigured(source, false)
    }
    const sources = structuredClone(statuses)
    return {
      id: `tenant-${source}-${key}`,
      sourceId: source,
      tenantKey: key,
      enabled: false,
      deleted: true,
      status: structuredClone(row),
      sources,
    }
  },
}
