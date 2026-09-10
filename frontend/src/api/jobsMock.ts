import type { JobCard, JobListQuery, JobSourceName, JobsApi, SourceStatus } from './jobsTypes'
import { canonicalKey, mergeJobs, matchesQuery, paginate, PAGE_SIZE, sourceDomain } from '../lib/jobs'

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
  },
  {
    source: 'lever',
    status: 'ok',
    lastSyncAt: hoursAgo(2),
    backoffUntil: null,
    errorMessage: null,
    progress: null,
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
    },
    {
      source: 'lever',
      status: 'ok',
      lastSyncAt: hoursAgo(2),
      backoffUntil: null,
      errorMessage: null,
      progress: null,
    },
  ]
}

export function simulateSourceError(source: JobSourceName, message: string) {
  statuses = statuses.map((item) =>
    item.source === source
      ? {
          ...item,
          status: 'error',
          backoffUntil: null,
          errorMessage: message,
          progress: null,
        }
      : item,
  )
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
      if (row.status === 'error') continue
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
      if (row.status === 'error') continue
      row.status = 'ok'
      row.lastSyncAt = new Date().toISOString()
      row.progress = null
    }
    return structuredClone(statuses)
  },
}
