import { describe, expect, it } from 'vitest'
import { mockEmailApi } from '../api/emailMock'
import { fillTemplate, leftoverVars, relativeTime, validateAttachments } from './email'

describe('email helpers', () => {
  it('fills template variables and reports leftovers', () => {
    const text = 'Hi {firstName} about {role} at {company} ({jobRef})'
    expect(fillTemplate(text, { firstName: 'Maya', company: 'Acme', role: 'Staff Engineer', jobRef: 'JOB-SE-1' })).toContain(
      'Maya',
    )
    expect(leftoverVars(fillTemplate(text, { firstName: 'Maya' })).sort()).toEqual(['company', 'jobRef', 'role'])
  })

  it('formats relative time', () => {
    const now = Date.parse('2026-09-09T12:00:00Z')
    expect(relativeTime('2026-09-09T11:50:00Z', now)).toBe('10m ago')
    expect(relativeTime('2026-09-09T10:00:00Z', now)).toBe('2h ago')
  })

  it('rejects oversized attachments', () => {
    const huge = new File([new Uint8Array(11 * 1024 * 1024)], 'huge.bin')
    expect(validateAttachments([huge]).error).toMatch(/10 MB/)
    const ok = new File([new Uint8Array(12)], 'ok.txt')
    expect(validateAttachments([ok]).error).toBeNull()
  })
})

describe('mock email api', () => {
  it('lists threads and clears unread on view', async () => {
    const page = await mockEmailApi.listThreads()
    expect(page.items.length).toBeGreaterThan(0)
    const unread = page.items.find((item) => item.unreadCount > 0)
    expect(unread).toBeTruthy()
    const messages = await mockEmailApi.listMessages(unread!.id)
    expect(messages.items.length).toBeGreaterThan(0)
    expect(messages.thread.unreadCount).toBe(0)
  })

  it('lists threads for the same job id the job feed mock uses', async () => {
    const page = await mockEmailApi.listJobThreads('job-1')
    expect(page.items.some((item) => item.jobId === 'job-1' && item.subject.includes('Staff Engineer'))).toBe(true)
  })
})
