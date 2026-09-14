import { labelledBy } from './sprint12'
import { isPhoneLayout } from './responsive'
import { STRINGS } from './i18n'

export function booleanSearch(items: Array<Record<string, string>>, q: string): Array<Record<string, string>> {
  const parts = q.split(/\s+/).filter((token) => token && token.toUpperCase() !== 'AND').map((token) => token.toLowerCase())
  if (!parts.length) return items
  return items.filter((row) => {
    const blob = Object.values(row).join(' ').toLowerCase()
    return parts.every((part) => blob.includes(part))
  })
}

export function whyNot(have: string[], need: string[]): { missing: string[] } {
  const haveSet = new Set(have.map((item) => item.toLowerCase()))
  return { missing: need.filter((item) => !haveSet.has(item.toLowerCase())) }
}

export function shortcuts(): Record<string, string> {
  return { j: 'next', k: 'prev', s: 'save', d: 'dismiss' }
}

export function compactNav(width: number): boolean {
  return isPhoneLayout(width)
}

export function enJobsLabel(): string {
  return STRINGS.en.jobs
}

export function sprint15Changelog(): { version: string; highlights: string[] }[] {
  return [{ version: '15.0.0', highlights: ['New boards (off)', 'Boolean search', 'Health v4'] }]
}

export function wcagName(kind: 'list' | 'detail' | 'filter'): { 'aria-label': string } {
  const labels = { list: 'Job results', detail: 'Job details', filter: 'Job filters' }
  return { 'aria-label': labels[kind], ...labelledBy(`${kind}-h`) }
}
