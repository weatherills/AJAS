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

export function reviewHref(opts: { matchId?: string | null; jobId?: string | null; pane?: 'details' | 'emails' } = {}): string {
  return hashHref('/review', {
    match: opts.matchId,
    job: opts.matchId ? undefined : opts.jobId,
    pane: opts.pane,
  })
}

export function emailHref(opts: { jobId?: string | null; threadId?: string | null } = {}): string {
  return hashHref('/email', { job: opts.jobId, thread: opts.threadId })
}

export function applyHref(requestId?: string | null, jobId?: string | null): string {
  const path = requestId ? `/apply/${encodeURIComponent(requestId)}` : '/apply'
  return hashHref(path, { job: jobId })
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
