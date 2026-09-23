import { describe, expect, it } from 'vitest'
import { FLAG_DEFAULTS, flagRows, mergeFlags } from './flags'

describe('feature flags', () => {
  it('turns tested connectors on and merges operator overrides', () => {
    expect(FLAG_DEFAULTS.workday_adapter).toBe(true)
    expect(FLAG_DEFAULTS.imap_transport).toBe(true)
    expect(FLAG_DEFAULTS.linkedin_easy_apply).toBe(true)
    expect(FLAG_DEFAULTS.ann_recall).toBe(false)
    expect(FLAG_DEFAULTS.gap_penalty).toBe(true)
    expect(FLAG_DEFAULTS.respect_robots).toBe(true)
    expect(FLAG_DEFAULTS.bulk_auto_apply).toBe(true)
    const merged = mergeFlags({ workday_adapter: false })
    expect(merged.workday_adapter).toBe(false)
    expect(flagRows(merged).some((row) => row.id === 'imap_transport' && row.on)).toBe(true)
  })
})
