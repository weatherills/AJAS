import { describe, expect, it } from 'vitest'
import { persistMatch20, sprint20Changelog } from './sprint20'

describe('sprint 20 helpers', () => {
  it('persists scores at or above 70', () => {
    expect(persistMatch20(70)).toBe(true)
    expect(persistMatch20(69.9)).toBe(false)
  })

  it('names sprint 20', () => {
    expect(sprint20Changelog()[0].version).toBe('20.0.0')
  })
})
