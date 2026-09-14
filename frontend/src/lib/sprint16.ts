import { labelledBy } from './sprint12'
import { isPhoneLayout } from './responsive'
import { STRINGS } from './i18n'

export function phraseSearch(items: Array<Record<string, string>>, q: string): Array<Record<string, string>> {
  const raw = q.trim()
  if (!raw) return items
  const notParts: string[] = []
  let buf = raw
  while (/\bNOT\s+/i.test(buf)) {
    const match = buf.match(/\bNOT\s+(\S+)/i)
    if (!match) break
    notParts.push(match[1].replace(/"/g, ''))
    buf = buf.replace(match[0], ' ')
  }
  const phrases = [...buf.matchAll(/"([^"]+)"/g)].map((item) => item[1].toLowerCase())
  const leftover = buf.replace(/"[^"]+"/g, ' ')
  const must = [
    ...phrases,
    ...leftover.split(/\s+/).filter((token) => token && token.toUpperCase() !== 'AND').map((token) => token.toLowerCase()),
  ]
  return items.filter((row) => {
    const blob = Object.values(row).join(' ').toLowerCase()
    return must.every((part) => blob.includes(part)) && notParts.every((part) => !blob.includes(part.toLowerCase()))
  })
}

export function skipLinks(): Record<string, string> {
  return { main: '#main', nav: '#nav', search: '#search' }
}

export function swipeActions(width: number): { enabled: boolean } {
  return { enabled: isPhoneLayout(width) }
}

export function enJobsLabel(): string {
  return STRINGS.en.jobs
}

export function sprint16Changelog(): { version: string; highlights: string[] }[] {
  return [{ version: '16.0.0', highlights: ['New boards (off)', 'Phrase/NOT search', 'Health v5'] }]
}

export function wcagName(kind: 'list' | 'detail' | 'filter'): { 'aria-label': string } {
  const labels = { list: 'Job results', detail: 'Job details', filter: 'Job filters' }
  return { 'aria-label': labels[kind], ...labelledBy(`${kind}-h`) }
}
