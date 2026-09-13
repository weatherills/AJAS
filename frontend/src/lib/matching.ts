export type MatchBand = 'red' | 'amber' | 'green'

export type MatchState = 'loading' | 'computed' | 'error' | 'no_resume' | 'insufficient'

export type MatchVersions = {
  algorithm: string
  embeddingsModel: string
  prompt: string
  keywordWeights: string
  normalization: string
}

export const CURRENT_ALGORITHM = 'weighted-0.4-0.6'
export const DEFAULT_THRESHOLD = 70
export const EXPLAIN_PREVIEW = 600
export const EXPLAIN_MAX = 2000
export const CHIP_VISIBLE = 6
export const TERM_TOOLTIP = 5

export const CURRENT_VERSIONS: MatchVersions = {
  algorithm: CURRENT_ALGORITHM,
  embeddingsModel: 'text-embedding-3-small',
  prompt: 'explain-v1',
  keywordWeights: 'kw-fields-v1',
  normalization: 'clamp-0-1',
}

const TOKEN = /[a-z0-9]+/g
const STOP = new Set([
  'a',
  'an',
  'the',
  'and',
  'or',
  'of',
  'to',
  'in',
  'for',
  'on',
  'with',
  'at',
  'by',
  'from',
  'as',
  'is',
  'are',
  'was',
  'were',
  'be',
  'this',
  'that',
  'it',
  'its',
  'job',
  'role',
  'full',
  'time',
  'remote',
])

export function tokenize(text: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of (text || '').toLowerCase().match(TOKEN) || []) {
    if (STOP.has(raw) || raw.length < 2) continue
    if (seen.has(raw)) continue
    seen.add(raw)
    out.push(raw)
  }
  return out
}

export function keywordOverlap(resume: string, job: string): number {
  const left = tokenize(resume)
  const right = new Set(tokenize(job))
  if (!left.length || !right.size) return 0
  const hits = left.filter((term) => right.has(term)).length
  return Math.round((1000 * hits) / left.length) / 10
}

export function matchedTerms(resume: string, job: string, limit = 8): string[] {
  const right = new Set(tokenize(job))
  return tokenize(resume).filter((term) => right.has(term)).slice(0, limit)
}

export function combineScore(keyword: number, semantic: number, keywordWeight = 0.4, semanticWeight = 0.6): number {
  const raw = keywordWeight * keyword + semanticWeight * semantic
  return Math.round(Math.max(0, Math.min(100, raw)) * 10) / 10
}

export function displayScore(score: number): number {
  return Math.round(score)
}

export function scoreBand(score: number): MatchBand {
  const shown = displayScore(score)
  if (shown >= 70) return 'green'
  if (shown >= 50) return 'amber'
  return 'red'
}

export function scoreLabel(score: number): string {
  const shown = displayScore(score)
  if (shown >= 70) return 'Good match'
  if (shown >= 50) return 'Fair match'
  return 'Poor match'
}

export type FitBucketKey = 'excellent' | 'strong' | 'promising' | 'fair' | 'poor'

export type FitBucket = {
  key: FitBucketKey
  label: string
  min: number
  score: number
  color: string
  tooltip: string
}

export const FIT_BUCKETS: Record<FitBucketKey, { label: string; min: number; color: string; tooltip: string }> = {
  excellent: {
    label: 'Excellent match',
    min: 85,
    color: '#34d399',
    tooltip: '85–100: strongest overlap on must-haves and recent experience.',
  },
  strong: {
    label: 'Strong match',
    min: 70,
    color: '#6ee7b7',
    tooltip: '70–84: likely a good fit; skim remaining gaps before applying.',
  },
  promising: {
    label: 'Promising match',
    min: 55,
    color: '#fbbf24',
    tooltip: '55–69: worth a closer look if the role is high priority.',
  },
  fair: {
    label: 'Fair match',
    min: 40,
    color: '#fb923c',
    tooltip: '40–54: partial overlap; tailor the resume before applying.',
  },
  poor: {
    label: 'Poor match',
    min: 0,
    color: '#fca5a5',
    tooltip: 'Below 40: missing core skills or seniority for this posting.',
  },
}

export function fitBucket(score: number): FitBucket {
  const shown = displayScore(score)
  const key: FitBucketKey =
    shown >= 85 ? 'excellent' : shown >= 70 ? 'strong' : shown >= 55 ? 'promising' : shown >= 40 ? 'fair' : 'poor'
  const meta = FIT_BUCKETS[key]
  return { key, label: meta.label, min: meta.min, score: shown, color: meta.color, tooltip: meta.tooltip }
}

export function evidenceSentences(resume: string, job: string, limit = 5): string[] {
  const resumeTerms = new Set(tokenize(resume))
  const parts = (job || '')
    .split(/(?<=[.!?])\s+|\n+/)
    .map((part) => part.replace(/\s+/g, ' ').trim())
    .filter((part) => part.length >= 24)
  const scored = parts
    .map((sentence, index) => {
      const overlap = tokenize(sentence).filter((term) => resumeTerms.has(term)).length
      return { sentence, overlap, index }
    })
    .filter((row) => row.overlap > 0)
    .sort((a, b) => b.overlap - a.overlap || a.index - b.index)
  const out: string[] = []
  const seen = new Set<string>()
  for (const row of scored) {
    const key = row.sentence.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(row.sentence.slice(0, 280))
    if (out.length >= limit) break
  }
  return out
}

export function meetsThreshold(score: number, threshold: number): boolean {
  return score >= threshold
}

export function truncateExplanation(text: string, limit = EXPLAIN_PREVIEW): { text: string; truncated: boolean } {
  const cleaned = (text || '').replace(/\r\n/g, '\n').trim()
  if (cleaned.length <= limit) return { text: cleaned, truncated: false }
  let cut = cleaned.slice(0, limit)
  const space = cut.lastIndexOf(' ')
  if (space > limit * 0.6) cut = cut.slice(0, space)
  return { text: cut.trimEnd(), truncated: true }
}

export function chipOverflow(terms: string[], visible = CHIP_VISIBLE): { shown: string[]; extra: number } {
  const unique = [...new Set(terms)]
  if (unique.length <= visible) return { shown: unique, extra: 0 }
  return { shown: unique.slice(0, visible), extra: unique.length - visible }
}

export function resumeHaystack(input: {
  skills?: string[]
  experience?: { title?: string | null; company?: string | null; description?: string | null }[]
  contact?: { fullName?: string | null } | null
}): string {
  const parts = [
    input.contact?.fullName || '',
    ...(input.skills || []),
    ...(input.experience || []).flatMap((item) => [item.title, item.company, item.description]),
  ]
  return parts.filter(Boolean).join(' ')
}

export function jobHaystack(input: {
  title: string
  company: string
  location?: string
  employmentType?: string
  snippet?: string
  description?: string
}): string {
  return [input.title, input.company, input.location, input.employmentType, input.description || input.snippet]
    .filter(Boolean)
    .join(' ')
}

export function explanationFor(score: number, terms: string[], gaps: string[]): string {
  const matched = terms.slice(0, 5).join(', ') || 'limited overlap'
  const missing = gaps.slice(0, 4).join(', ')
  const lines = [
    `This role scores ${displayScore(score)}% against your resume using keyword and semantic signals.`,
    `Strongest overlap: ${matched}.`,
  ]
  if (missing) lines.push(`Gaps to review: ${missing}.`)
  lines.push('Weights are 40% keywords and 60% semantic similarity on a 0–100 scale.')
  return lines.join('\n')
}

export function isOutdated(versions: MatchVersions | null | undefined): boolean {
  if (!versions?.algorithm) return false
  return versions.algorithm !== CURRENT_ALGORITHM
}

export function formatUtc(stamp: string | null | undefined): string {
  if (!stamp) return 'Unknown'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return `${date.toISOString().replace('.000Z', 'Z')} UTC`
}

export function parseThresholdInput(raw: string): { value: number | null; error: string | null } {
  const trimmed = raw.trim()
  if (trimmed === '') return { value: null, error: 'Enter an integer from 0 to 100' }
  if (!/^-?\d+$/.test(trimmed)) return { value: null, error: 'Enter an integer from 0 to 100' }
  const value = Number.parseInt(trimmed, 10)
  if (value < 0 || value > 100) return { value: null, error: 'Enter an integer from 0 to 100' }
  return { value, error: null }
}

export function storedMatchesForJobs<T extends { jobId: string }>(
  jobIds: string[],
  stored: T[],
): { known: T[]; missingIds: string[] } {
  const byId = new Map(stored.map((row) => [row.jobId, row]))
  const known: T[] = []
  const missingIds: string[] = []
  for (const jobId of jobIds) {
    const row = byId.get(jobId)
    if (row) known.push(row)
    else missingIds.push(jobId)
  }
  return { known, missingIds }
}
