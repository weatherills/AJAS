import { describe, expect, it } from 'vitest'
import { persistMatch, sprint19Changelog } from './sprint19'

describe('sprint 19 helpers', () => {
  it('persists scores at or above 70', () => {
    expect(persistMatch(70)).toBe(true)
    expect(persistMatch(69.9)).toBe(false)
  })

  it('names sprint 19', () => {
    expect(sprint19Changelog()[0].version).toBe('19.0.0')
  })
})
