import { describe, expect, it } from 'vitest'
import { clampThreshold100, compositeScore100, sprint18Changelog } from './sprint18'

describe('sprint 18 helpers', () => {
  it('clamps 0–100 match thresholds', () => {
    expect(clampThreshold100(140)).toBe(100)
    expect(clampThreshold100(-1)).toBe(0)
    expect(clampThreshold100(70)).toBe(70)
  })

  it('combines keyword and semantic scores on a 0–100 scale', () => {
    expect(compositeScore100(1, 1)).toBe(100)
    expect(compositeScore100(0, 1, 0.4, 0.6)).toBe(60)
  })

  it('names sprint 18', () => {
    expect(sprint18Changelog()[0].version).toBe('18.0.0')
  })
})
