import { describe, expect, it } from 'vitest'
import { evaluateLimit } from './automationLimits'

describe('automation limits', () => {
  it('requires consent and enforces per-site caps', () => {
    expect(evaluateLimit({ site: 'greenhouse', cap: 20, consent: false, used: 0 }).reason).toBe('consent')
    expect(evaluateLimit({ site: 'greenhouse', cap: 2, consent: true, used: 2 }).reason).toBe('cap')
    expect(evaluateLimit({ site: 'lever', cap: 20, consent: true, used: 1 }).allowed).toBe(true)
  })
})
