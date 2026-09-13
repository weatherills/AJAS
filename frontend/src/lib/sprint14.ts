import { labelledBy } from './sprint12'
import { isPhoneLayout } from './responsive'
import { STRINGS } from './i18n'

export function counterfactual(have: string[], need: string[]): { add: string[]; suggestion: string } {
  const haveSet = new Set(have.map((item) => item.toLowerCase()))
  const add = need.filter((item) => !haveSet.has(item.toLowerCase()))
  return { add, suggestion: add.length ? `Add ${add.join(', ')}` : 'Add no extra skills' }
}

export function missingMustHaves(resume: string[], required: string[]): string[] {
  const have = new Set(resume.map((item) => item.toLowerCase()))
  return required.filter((item) => !have.has(item.toLowerCase()))
}

export function subScores(keyword: number, semantic: number, recency: number): { total: number } {
  return { total: Math.round((0.5 * keyword + 0.4 * semantic + 0.1 * recency) * 1000) / 1000 }
}

export function searchNormalized(items: Array<Record<string, string>>, q: string): Array<Record<string, string>> {
  const needle = q.trim().toLowerCase()
  if (!needle) return items
  return items.filter((row) => Object.values(row).join(' ').toLowerCase().includes(needle))
}

export function toastDigest(items: string[]): { count: number; channel: string } {
  return { count: items.length, channel: 'email' }
}

export function wcagName(kind: 'list' | 'detail' | 'filter'): { 'aria-label': string } {
  const labels = { list: 'Job results', detail: 'Job details', filter: 'Job filters' }
  return { 'aria-label': labels[kind], ...labelledBy(`${kind}-h`) }
}

export function enJobsLabel(): string {
  return STRINGS.en.jobs
}

export function sprint14Changelog(): { version: string; highlights: string[] }[] {
  return [{ version: '14.0.0', highlights: ['New adapters (off)', 'Counterfactuals', 'Health v3'] }]
}

export function phoneLayout(width: number): boolean {
  return isPhoneLayout(width)
}
