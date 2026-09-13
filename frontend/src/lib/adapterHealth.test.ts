import { describe, expect, it } from 'vitest'
import { adapterHealthRows, toggleMute } from './adapterHealth'

describe('adapter health dashboard', () => {
  it('tracks last success, drift, and mute', () => {
    const rows = adapterHealthRows()
    expect(rows.find((row) => row.source === 'workday')?.drift).toBe(true)
    const muted = toggleMute(rows, 'workday')
    expect(muted.find((row) => row.source === 'workday')?.muted).toBe(true)
  })
})
