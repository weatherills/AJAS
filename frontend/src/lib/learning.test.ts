import { describe, expect, it } from 'vitest'
import { mockLearningApi } from '../api/learningMock'
import { asStrictness, percent, STRICTNESS_HELP } from './learning'

describe('learning helpers', () => {
  it('maps slider stops', () => {
    expect(asStrictness(-1)).toBe(0)
    expect(asStrictness(1)).toBe(1)
    expect(asStrictness(9)).toBe(2)
    expect(STRICTNESS_HELP[0]).toMatch(/precision/)
  })

  it('formats percents', () => {
    expect(percent(0.75)).toBe('75%')
  })
})

describe('mock learning api', () => {
  it('returns metrics and updates manual strictness', async () => {
    const metrics = await mockLearningApi.metrics('7d')
    expect(metrics.decisions).toBeGreaterThan(0)
    expect(metrics.empty).toBe(false)
    const patched = await mockLearningApi.patchParams({ tuningMode: 'manual', strictness: 0 })
    expect(patched.tuningMode).toBe('manual')
    expect(patched.score_threshold).toBe(0.8)
  })
})
