import { json, request } from './live'
import type { JobDetail, JobListPage, JobListQuery, JobSourceName, JobsApi, SourceStatus } from './jobsTypes'

function queryString(query: JobListQuery): string {
  const params = new URLSearchParams()
  params.set('sources', query.sources.join(',') || 'none')
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
    const id = source === 'all' ? 'greenhouse' : source
    await json(await request(`/api/v1/sources/${id}/crawl`, { method: 'POST' }))
    if (source === 'all') {
      await json(await request('/api/v1/sources/lever/crawl', { method: 'POST' }))
    }
    return json<SourceStatus[]>(await request('/api/v1/sources/status'))
  },
}
