import { describe, expect, it } from 'vitest'
import { formatNumber, formatPercent } from './format'
import { cycleTheme, resolveTheme } from './theme'
import { defaultChoices, saveChoices } from './cookieConsent'
import {
  labelledBy,
  tableToCardLayout,
  enqueueOffline,
  replayOffline,
  exportCsv,
  applyQuery,
  emptyCopy,
  tourSteps,
  searchHelp,
  changelogEntries,
} from './sprint12'


describe('locale formats', () => {
  it('formats numbers with the active locale tag', () => {
    expect(formatNumber(1234, 'en')).toMatch(/1[,.]234/)
    expect(formatPercent(0.8, 'en')).toMatch(/80/)
  })
})

describe('theme toggle', () => {
  it('resolves system preference and cycles dark/light/system', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
    expect(cycleTheme('system')).toBe('dark')
    expect(cycleTheme('dark')).toBe('light')
    expect(cycleTheme('light')).toBe('system')
  })
})

describe('cookie banner', () => {
  it('keeps necessary cookies on and marketing off by default', () => {
    expect(defaultChoices().necessary).toBe(true)
    expect(defaultChoices().marketing).toBe(false)
    const saved = saveChoices({ necessary: true, analytics: true, marketing: false })
    expect(saved.analytics).toBe(true)
    expect(saved.necessary).toBe(true)
  })
})
describe('sprint12 product helpers', () => {
  it('covers landed Sprint 12 UI helpers', () => {
    expect(labelledBy('help-h')['aria-labelledby']).toBe('help-h')
    expect(tableToCardLayout(390)).toBe('cards')
    expect(tableToCardLayout(900)).toBe('table')
    const queued = enqueueOffline([], { id: 'a1', type: 'apply', payload: {} })
    expect(replayOffline(queued).replayed).toEqual(['a1'])
    expect(exportCsv([{ title: 'Staff', score: 91 }], ['title', 'score'])).toContain('title,score')
    expect(applyQuery([{ title: 'Staff Python', company: 'Acme' }, { title: 'PM', company: 'Other' }], [{ field: 'title', op: 'regex', value: '^Staff' }])).toHaveLength(1)
    expect(emptyCopy('jobs')).toMatch(/Greenhouse/)
    expect(tourSteps()[0].href).toBe('#/resumes')
    expect(searchHelp([{ id: 'threshold', title: 'Match threshold', body: 'slider' }], 'thresh')[0].id).toBe('threshold')
    expect(changelogEntries()[0].version).toBe('12.0.0')
  })
})
