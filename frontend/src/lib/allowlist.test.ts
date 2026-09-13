import { describe, expect, it } from 'vitest'
import { formatAllowlist, parseAllowlist, recordAllowlistAudit } from './allowlist'

describe('outbound allowlist', () => {
  it('parses admin policy hosts', () => {
    expect(parseAllowlist('Boards.greenhouse.io, jobs.lever.co')).toEqual(['boards.greenhouse.io', 'jobs.lever.co'])
    expect(formatAllowlist(['jobs.lever.co', 'boards.greenhouse.io'])).toBe('boards.greenhouse.io, jobs.lever.co')
    expect(recordAllowlistAudit('ada', 'jobs.lever.co').action).toBe('allowlist.update')
  })
})
