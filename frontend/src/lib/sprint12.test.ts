import { describe, expect, it } from 'vitest'
import { formatNumber, formatPercent } from './format'
import {
  labelledBy,
} from './sprint12'


describe('locale formats', () => {
  it('formats numbers with the active locale tag', () => {
    expect(formatNumber(1234, 'en')).toMatch(/1[,.]234/)
    expect(formatPercent(0.8, 'en')).toMatch(/80/)
  })
})
describe('sprint12 product helpers', () => {
  it('covers landed Sprint 12 UI helpers', () => {
    expect(labelledBy('help-h')['aria-labelledby']).toBe('help-h')
  })
})
