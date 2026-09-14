import { describe, expect, it } from 'vitest'
import { clampThreshold, compositeScore, reviewQueueQuery, sprint17Changelog } from './sprint17'

describe('sprint 17 helpers', () => {
  it('clamps match thresholds', () => {
    expect(clampThreshold(1.4)).toBe(1)
    expect(clampThreshold(-1)).toBe(0)
    expect(clampThreshold(0.7)).toBe(0.7)
  })

  it('combines keyword and semantic scores', () => {
    expect(compositeScore(1, 1)).toBe(1)
    expect(compositeScore(0, 1, 0.4, 0.6)).toBe(0.6)
  })

  it('builds the review queue query', () => {
    expect(reviewQueueQuery({ min: 0.7, q: 'python' })).toBe('/v1/matches?min=0.7&q=python')
  })

  it('names sprint 17', () => {
    expect(sprint17Changelog()[0].version).toBe('17.0.0')
  })
})
