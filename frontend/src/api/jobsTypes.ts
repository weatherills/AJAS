export type JobSourceName = 'greenhouse' | 'lever'

export type SourceSyncStatus = 'ok' | 'syncing' | 'rate_limited' | 'error' | 'unconfigured'

export type JobSourceRef = {
  source: JobSourceName
  sourceUrl: string
  postedAt: string | null
  domain: string
}

export type JobCard = {
  id: string
  canonicalKey: string
  title: string
  company: string
  location: string
  employmentType: string
  snippet: string
  applyUrl: string
  updatedAt: string
  isNew: boolean
  sources: JobSourceRef[]
  primarySource: JobSourceName
}

export type JobDetail = JobCard & {
  description: string
  descriptionError?: string | null
}

export type SourceStatus = {
  source: JobSourceName
  status: SourceSyncStatus
  lastSyncAt: string | null
  backoffUntil: string | null
  errorMessage: string | null
  progress: string | null
  configured?: boolean
  tenantCount?: number
}

export type JobStatusFilter = 'all' | 'new'

export type JobListQuery = {
  sources: JobSourceName[]
  q: string
  location: string
  status: JobStatusFilter
  cursor: string | null
  limit: number
  since?: string | null
}

export type JobListPage = {
  items: JobCard[]
  nextCursor: string | null
  total: number
}

export type JobFilters = {
  sources: JobSourceName[]
  q: string
  location: string
  status: JobStatusFilter
  pagination: 'infinite' | 'pages'
}

export type JobsApi = {
  list(query: JobListQuery): Promise<JobListPage>
  get(id: string): Promise<JobDetail>
  sourceStatus(): Promise<SourceStatus[]>
  refresh(source: JobSourceName | 'all'): Promise<SourceStatus[]>
}
