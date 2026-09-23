import { json, request } from './live'
import type { AddTenantBody, AddTenantResult, JobDetail, JobListPage, JobListQuery, JobSourceName, JobsApi, SourceStatus } from './jobsTypes'
import { cosmosSources, feedSourcesQueryParam, isCosmosSource, mergeJobs } from '../lib/jobs'
import { linkedinStatusRow, loadLinkedInAccountId } from '../lib/linkedin'
import { liveLinkedInApi } from './linkedinLive'

const LI_DETAIL = new Map<string, JobDetail>()

export function jobsListQueryString(query: JobListQuery): string {
  const params = new URLSearchParams()
  params.set('sources', feedSourcesQueryParam(cosmosSources(query.sources)))
  if (query.q) params.set('q', query.q)
  if (query.location) params.set('location', query.location)
  if (query.status) params.set('status', query.status)
  if (query.cursor) params.set('cursor', query.cursor)
  params.set('limit', String(query.limit))
  if (query.since) params.set('since', query.since)
  return params.toString()
}

function cacheLinkedIn(items: JobDetail[] | JobListPage['items']): void {
  for (const item of items) {
    if (item.primarySource !== 'linkedin') continue
    LI_DETAIL.set(item.id, {
      ...item,
      description: 'description' in item && typeof item.description === 'string' ? item.description : item.snippet,
    })
  }
}

async function linkedinPage(query: JobListQuery): Promise<{ items: JobListPage['items']; reason: string }> {
  const result = await liveLinkedInApi.search({
    live: true,
    keywords: query.q,
    location: query.location,
    accountId: loadLinkedInAccountId(),
  })
  cacheLinkedIn(result.jobs)
  return { items: result.jobs, reason: result.reason }
}

async function linkedinSourceRow(): Promise<SourceStatus> {
  try {
    const status = await liveLinkedInApi.status()
    return linkedinStatusRow({
      adapterOn: status.flags?.linkedin_adapter,
      easyApplyOn: status.flags?.linkedin_easy_apply,
      live: status.linkedinLive,
      accounts: status.linkedinAccounts,
    })
  } catch {
    return linkedinStatusRow({ adapterOn: true, live: false })
  }
}

export const liveJobsApi: JobsApi = {
  async list(query) {
    const wantLinkedIn = query.sources.includes('linkedin')
    const board = cosmosSources(query.sources)
    const cosmos =
      board.length > 0
        ? await json<JobListPage>(await request(`/api/v1/jobs?${jobsListQueryString({ ...query, sources: board })}`))
        : { items: [], nextCursor: null, total: 0 }
    if (!wantLinkedIn || query.cursor) return cosmos
    try {
      const extra = await linkedinPage(query)
      const items = mergeJobs([...cosmos.items, ...extra.items])
      return { items, nextCursor: cosmos.nextCursor, total: items.length }
    } catch {
      return cosmos
    }
  },
  async get(id) {
    const cached = LI_DETAIL.get(id)
    try {
      return await json<JobDetail>(await request(`/api/v1/jobs/${encodeURIComponent(id)}`))
    } catch (err) {
      if (cached) return cached
      throw err
    }
  },
  async sourceStatus() {
    const rows = await json<SourceStatus[]>(await request('/api/v1/sources/status'))
    const linkedin = await linkedinSourceRow()
    return [...rows.filter((row) => row.source !== 'linkedin'), linkedin]
  },
  async refresh(source: JobSourceName | 'all') {
    const ids: JobSourceName[] =
      source === 'all' ? ['greenhouse', 'lever'] : isCosmosSource(source) ? [source] : []
    if (source === 'all' || source === 'linkedin') {
      try {
        await liveLinkedInApi.search({
          live: true,
          accountId: loadLinkedInAccountId(),
        })
      } catch {
        /* LinkedIn extra-board refresh is additive; GH/Lever crawl still runs */
      }
    }
    for (const id of ids) {
      const resp = await request(`/api/v1/sources/${id}/crawl`, { method: 'POST' })
      if (resp.status === 404) {
        await resp.json().catch(() => ({}))
        continue
      }
      await json(resp)
    }
    return json<SourceStatus[]>(await request('/api/v1/sources/status')).then(async (rows) => {
      const linkedin = await linkedinSourceRow()
      return [...rows.filter((row) => row.source !== 'linkedin'), linkedin]
    })
  },
  async refreshTenant(source: JobSourceName, tenantKey: string) {
    await json(
      await request(`/api/v1/sources/${source}/tenants/${encodeURIComponent(tenantKey)}/crawl`, {
        method: 'POST',
      }),
    )
    return json<SourceStatus[]>(await request('/api/v1/sources/status'))
  },
  async addTenant(source: JobSourceName, body: AddTenantBody) {
    return json<AddTenantResult>(
      await request(`/api/v1/sources/${source}/tenants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async removeTenant(source: JobSourceName, tenantKey: string) {
    return json<AddTenantResult>(
      await request(`/api/v1/sources/${source}/tenants/${encodeURIComponent(tenantKey)}`, {
        method: 'DELETE',
      }),
    )
  },
}
