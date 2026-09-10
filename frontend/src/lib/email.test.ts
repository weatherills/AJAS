import { describe, expect, it } from 'vitest'
import { mockEmailApi, setEmailSuggestFail } from '../api/emailMock'
import { demoMailbox, fillTemplate, graphConnected, leftoverVars, mailboxReadable, oauthConfigured, relativeTime, validateAttachments } from './email'

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

describe('mailbox connection helpers', () => {
  it('treats Graph OAuth as connected and demo as a separate mailbox', () => {
    expect(graphConnected({ connected: false, graphConnected: false, address: null, lastSyncedAt: null, unreadCount: 0, demo: false })).toBe(
      false,
    )
    expect(
      mailboxReadable({ connected: false, graphConnected: false, address: null, lastSyncedAt: null, unreadCount: 0, demo: false }),
    ).toBe(false)
    const demo = {
      connected: false,
      graphConnected: false,
      address: 'local-user@ajas.dev',
      lastSyncedAt: null,
      unreadCount: 1,
      demo: true,
      provider: 'demo' as const,
    }
    expect(graphConnected(demo)).toBe(false)
    expect(demoMailbox(demo)).toBe(true)
    expect(mailboxReadable(demo)).toBe(true)
    const graph = {
      connected: true,
      graphConnected: true,
      address: 'jane@contoso.com',
      lastSyncedAt: null,
      unreadCount: 0,
      demo: false,
      provider: 'microsoft365' as const,
    }
    expect(graphConnected(graph)).toBe(true)
    expect(demoMailbox(graph)).toBe(false)
    expect(mailboxReadable(graph)).toBe(true)
  })

  it('does not treat a demo flag as Graph when connected is true', () => {
    const mixed = {
      connected: true,
      address: 'local-user@ajas.dev',
      lastSyncedAt: null,
      unreadCount: 0,
      demo: true,
    }
    expect(graphConnected(mixed)).toBe(false)
    expect(demoMailbox(mixed)).toBe(true)
  })

  it('treats missing oauthConfigured as available and false as unconfigured', () => {
    expect(
      oauthConfigured({
        connected: false,
        graphConnected: false,
        address: null,
        lastSyncedAt: null,
        unreadCount: 0,
        demo: false,
      }),
    ).toBe(true)
    expect(
      oauthConfigured({
        connected: false,
        graphConnected: false,
        address: 'local-user@ajas.dev',
        lastSyncedAt: null,
        unreadCount: 1,
        demo: true,
        oauthConfigured: false,
      }),
    ).toBe(false)
  })
})

describe('mock email api', () => {
  it('reports a demo mailbox, not a connected Graph account', async () => {
    const status = await mockEmailApi.status()
    expect(graphConnected(status)).toBe(false)
    expect(demoMailbox(status)).toBe(true)
    expect(mailboxReadable(status)).toBe(true)
    expect(status.oauthConfigured).toBe(true)
  })

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

  it('includes thread participants on list rows', async () => {
    const page = await mockEmailApi.listThreads()
    expect(page.items.every((item) => Array.isArray(item.participants) && item.participants.length > 0)).toBe(true)
    const staff = page.items.find((item) => item.id === 't-staff')
    expect(staff?.participants).toContain('maya@acme.test')
  })

  it('surfaces suggestion failures from the mock composer', async () => {
    setEmailSuggestFail('Suggestion limit reached for today. Try again tomorrow.')
    await expect(mockEmailApi.suggestions('t-staff')).rejects.toThrow(/Suggestion limit reached/)
  })
})
