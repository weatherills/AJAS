import { json, request } from './live'
import type { AddTenantBody, AddTenantResult, JobDetail, JobListPage, JobListQuery, JobSourceName, JobsApi, SourceStatus } from './jobsTypes'
import { feedSourcesQueryParam } from '../lib/jobs'

function queryString(query: JobListQuery): string {
  const params = new URLSearchParams()
  params.set('sources', feedSourcesQueryParam(query.sources))
  if (query.q) params.set('q', query.q)
  if (query.location) params.set('location', query.location)
  if (query.status) params.set('status', query.status)
  if (query.cursor) params.set('cursor', query.cursor)
  params.set('limit', String(query.limit))
  if (query.since) params.set('since', query.since)
  return params.toString()
}

export const liveJobsApi: JobsApi = {
  async list(query) {
    return json<JobListPage>(await request(`/api/v1/jobs?${queryString(query)}`))
  },
  async get(id) {
    return json<JobDetail>(await request(`/api/v1/jobs/${encodeURIComponent(id)}`))
  },
  async sourceStatus() {
    return json<SourceStatus[]>(await request('/api/v1/sources/status'))
  },
  async refresh(source: JobSourceName | 'all') {
    const ids = source === 'all' ? (['greenhouse', 'lever'] as const) : [source]
    for (const id of ids) {
      const resp = await request(`/api/v1/sources/${id}/crawl`, { method: 'POST' })
      if (resp.status === 404) {
        await resp.json().catch(() => ({}))
        continue
      }
      await json(resp)
    }
    return json<SourceStatus[]>(await request('/api/v1/sources/status'))
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
