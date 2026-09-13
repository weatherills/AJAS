import { describe, expect, it } from 'vitest'
import { formatNumber, formatPercent } from './format'
import { cycleTheme, resolveTheme } from './theme'
import {
  labelledBy,
  tableToCardLayout,
  enqueueOffline,
  replayOffline,
  exportCsv,
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
describe('sprint12 product helpers', () => {
  it('covers landed Sprint 12 UI helpers', () => {
    expect(labelledBy('help-h')['aria-labelledby']).toBe('help-h')
    expect(tableToCardLayout(390)).toBe('cards')
    expect(tableToCardLayout(900)).toBe('table')
    const queued = enqueueOffline([], { id: 'a1', type: 'apply', payload: {} })
    expect(replayOffline(queued).replayed).toEqual(['a1'])
    expect(exportCsv([{ title: 'Staff', score: 91 }], ['title', 'score'])).toContain('title,score')
  })
})
