import { describe, expect, it } from 'vitest'
import { auditCsv, filterAudit } from './audit'

describe('audit trail', () => {
  it('filters by actor/action/date and exports CSV', () => {
    const rows = [
      { at: '2026-09-13T10:00:00Z', actor: 'ada', action: 'ingest', target: 'job-1' },
      { at: '2026-09-13T12:00:00Z', actor: 'linus', action: 'apply', target: 'job-2' },
    ]
    const filtered = filterAudit(rows, { actor: 'ada', action: 'ingest' })
    expect(filtered).toHaveLength(1)
    expect(auditCsv(filtered)).toContain('ingest')
  })
})
