import { describe, expect, it } from 'vitest'
import type { EmailThread } from '../api/emailTypes'
import { groupThreads } from './threadGroups'

function thread(id: string, jobId: string | null, jobTitle: string | null): EmailThread {
  return {
    id,
    subject: id,
    jobId,
    jobTitle,
    jobCompany: null,
    linked: Boolean(jobId),
    linkSource: null,
    linkConfidence: null,
    lastMessageAt: '2026-09-13T10:00:00Z',
    unreadCount: 0,
    snippet: 'hi',
    participants: [],
  }
}

describe('inbox smart grouping', () => {
  it('groups threads by job and keeps unlinked together', () => {
    const groups = groupThreads([
      thread('t1', 'job-1', 'Staff Engineer'),
      thread('t2', 'job-1', 'Staff Engineer'),
      thread('t3', null, null),
    ])
    expect(groups).toHaveLength(2)
    expect(groups[0].label).toBe('Staff Engineer')
    expect(groups[0].items).toHaveLength(2)
    expect(groups[1].key).toBe('unlinked')
  })
})
