import { describe, expect, it } from 'vitest'
import { formatAllowlist, parseAllowlist } from './allowlist'

describe('outbound allowlist', () => {
  it('parses admin policy hosts', () => {
    expect(parseAllowlist('Boards.greenhouse.io, jobs.lever.co')).toEqual(['boards.greenhouse.io', 'jobs.lever.co'])
    expect(formatAllowlist(['jobs.lever.co', 'boards.greenhouse.io'])).toBe('boards.greenhouse.io, jobs.lever.co')
  })
})
