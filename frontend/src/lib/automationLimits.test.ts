import { describe, expect, it } from 'vitest'
import { evaluateLimit, remainingInWindow, windowLabel } from './automationLimits'

describe('automation limits', () => {
  it('requires consent and enforces per-site caps', () => {
    expect(evaluateLimit({ site: 'greenhouse', cap: 20, consent: false, used: 0 }).reason).toBe('consent')
    expect(evaluateLimit({ site: 'greenhouse', cap: 2, consent: true, used: 2 }).reason).toBe('cap')
    expect(evaluateLimit({ site: 'lever', cap: 20, consent: true, used: 1 }).allowed).toBe(true)
  })

  it('reports remaining applies in the site window', () => {
    expect(remainingInWindow({ site: 'greenhouse', cap: 10, consent: true, used: 3, windowMinutes: 60 })).toBe(7)
    expect(windowLabel({ site: 'greenhouse', cap: 10, consent: true, used: 0, windowMinutes: 60 })).toBe('60m')
    expect(windowLabel({ site: 'lever', cap: 10, consent: true, used: 0 })).toBe('daily')
  })
})
