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
