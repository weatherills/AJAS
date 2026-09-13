import { describe, expect, it } from 'vitest'
import { dashboardPreview } from './sourceQuotas'

describe('source quotas', () => {
  it('flags cap hits on the ops dashboard', () => {
    const rows = dashboardPreview()
    expect(rows.some((row) => row.source === 'greenhouse')).toBe(true)
    expect(rows.find((row) => row.source === 'workday')?.capHit).toBe(true)
  })
})
