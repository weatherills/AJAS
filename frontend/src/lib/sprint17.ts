/** Sprint 17 review/matching helpers used by Review and Settings. */

export function clampThreshold(value: number, min = 0, max = 1): number {
  if (Number.isNaN(value)) return 0.7
  return Math.min(max, Math.max(min, value))
}

export function compositeScore(keyword: number, semantic: number, keywordWeight = 0.4, semanticWeight = 0.6): number {
  return Number((keyword * keywordWeight + semantic * semanticWeight).toFixed(4))
}

export function reviewQueueQuery(opts: { min?: number; q?: string; status?: string; cursor?: string } = {}): string {
  const params = new URLSearchParams()
  if (opts.min != null) params.set('min', String(opts.min))
  if (opts.q) params.set('q', opts.q)
  if (opts.status && opts.status !== 'awaiting') params.set('status', opts.status)
  if (opts.cursor) params.set('cursor', opts.cursor)
  const qs = params.toString()
  return `/v1/matches${qs ? `?${qs}` : ''}`
}

export function sprint17Changelog(): { version: string; highlights: string[] }[] {
  return [
    {
      version: '17.0.0',
      highlights: ['Greenhouse/Lever ingest', 'Match + review APIs', 'Graph mail + Auto-Apply'],
    },
  ]
}
