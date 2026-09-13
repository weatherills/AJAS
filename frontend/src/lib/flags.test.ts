import { describe, expect, it } from 'vitest'
import { FLAG_DEFAULTS, flagRows, mergeFlags } from './flags'

describe('feature flags', () => {
  it('keeps optional adapters off and merges operator overrides', () => {
    expect(FLAG_DEFAULTS.workday_adapter).toBe(false)
    expect(FLAG_DEFAULTS.respect_robots).toBe(true)
    const merged = mergeFlags({ workday_adapter: true })
    expect(merged.workday_adapter).toBe(true)
    expect(flagRows(merged).some((row) => row.id === 'workday_adapter' && row.on)).toBe(true)
  })
})
