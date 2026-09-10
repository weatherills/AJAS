import { useEffect, useState } from 'react'

export type HashSearch = {
  path: string
  params: URLSearchParams
}

export function parseHash(hash: string): HashSearch {
  const raw = hash.replace(/^#/, '') || '/'
  const [pathPart, query = ''] = raw.split('?')
  const path = pathPart.startsWith('/') ? pathPart : `/${pathPart}`
  return { path: path || '/', params: new URLSearchParams(query) }
}

export function hashHref(path: string, params: Record<string, string | null | undefined> = {}): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) qs.set(key, value)
  }
  const query = qs.toString()
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `#${normalized}${query ? `?${query}` : ''}`
}

export function jobHref(jobId: string, tab?: 'details' | 'emails'): string {
  return hashHref('/jobs', { job: jobId, tab })
}

export type ReviewHashTab = 'matches' | 'saved' | 'history'

export function parseReviewTab(raw: string | null | undefined): ReviewHashTab {
  if (raw === 'saved' || raw === 'history') return raw
  return 'matches'
}

export function reviewHref(
  opts: {
    matchId?: string | null
    jobId?: string | null
    resumeId?: string | null
    pane?: 'details' | 'emails'
    tab?: ReviewHashTab | null
    min?: number | null
    max?: number | null
    company?: string | null
    loc?: string | null
    q?: string | null
    sort?: string | null
    source?: string | null
    status?: string | null
    after?: string | null
  } = {},
): string {
  return hashHref('/review', {
    tab: opts.tab && opts.tab !== 'matches' ? opts.tab : undefined,
    match: opts.matchId,
    job: opts.matchId ? undefined : opts.jobId,
    resume: opts.resumeId,
    pane: opts.pane,
    min: opts.min != null && opts.min !== 0 ? String(opts.min) : undefined,
    max: opts.max != null && opts.max !== 100 ? String(opts.max) : undefined,
    company: opts.company,
    loc: opts.loc,
    q: opts.q,
    sort: opts.sort && opts.sort !== 'score' ? opts.sort : undefined,
    source: opts.source && opts.source !== 'all' && opts.source !== 'ai' ? opts.source : undefined,
    status: opts.status && opts.status !== 'awaiting' && opts.status !== 'all' ? opts.status : undefined,
    after: opts.after,
  })
}

export function emailHref(opts: { jobId?: string | null; threadId?: string | null } = {}): string {
  return hashHref('/email', { job: opts.jobId, thread: opts.threadId })
}

export function applyHref(requestId?: string | null, jobId?: string | null): string {
  const path = requestId ? `/apply/${encodeURIComponent(requestId)}` : '/apply'
  return hashHref(path, { job: jobId })
}

export function resumeHref(resumeId: string): string {
  return hashHref(`/resumes/${encodeURIComponent(resumeId)}/edit`)
}

export function useHashSearch(): URLSearchParams {
  const [params, setParams] = useState(() => parseHash(window.location.hash).params)
  useEffect(() => {
    const onHash = () => setParams(parseHash(window.location.hash).params)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return params
}
