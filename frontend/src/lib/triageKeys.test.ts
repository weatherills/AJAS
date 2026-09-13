import { describe, expect, it } from 'vitest'
import { TRIAGE_HELP, triageShortcut } from './triageKeys'

describe('triage keyboard shortcuts', () => {
  it('maps j/k/a/d/s/c/? and ignores fields', () => {
    expect(triageShortcut({ key: 'j' })).toBe('next')
    expect(triageShortcut({ key: 'k' })).toBe('prev')
    expect(triageShortcut({ key: 'a' })).toBe('apply')
    expect(triageShortcut({ key: 'Enter' })).toBe('apply')
    expect(triageShortcut({ key: 'y' })).toBe('apply')
    expect(triageShortcut({ key: 'd' })).toBe('dismiss')
    expect(triageShortcut({ key: 's' })).toBe('save')
    expect(triageShortcut({ key: 'c' })).toBe('compare')
    expect(triageShortcut({ key: '?' })).toBe('why')
    expect(triageShortcut({ key: 'j', target: { tagName: 'INPUT' } })).toBeNull()
    expect(triageShortcut({ key: 'a', metaKey: true })).toBeNull()
    expect(TRIAGE_HELP).toContain('j/k')
    expect(TRIAGE_HELP).toMatch(/accept/)
  })
})
