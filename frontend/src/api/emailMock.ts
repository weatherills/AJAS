import type { EmailApi, EmailMessage, EmailStatus, EmailTemplate, EmailThread } from './emailTypes'

const mailbox: EmailStatus = {
  connected: true,
  address: 'local-user@ajas.dev',
  lastSyncedAt: new Date().toISOString(),
  unreadCount: 1,
  demo: true,
}

const templates: EmailTemplate[] = [
  { id: 'thanks', name: 'Thanks', body: 'Hi {firstName},\n\nThanks for reaching out about the {role} role at {company} ({jobRef}).' },
  { id: 'followup', name: 'Follow-up', body: 'Hi {firstName},\n\nJust following up on {role} at {company}.' },
  { id: 'availability', name: 'Availability', body: 'Hi {firstName},\n\nI am available to talk about {role} at {company}.' },
]

function thread(partial: Partial<EmailThread> & Pick<EmailThread, 'id' | 'subject'>): EmailThread {
  return {
    jobId: null,
    jobTitle: null,
    jobCompany: null,
    linked: Boolean(partial.jobId),
    linkSource: partial.jobId ? 'rule' : null,
    linkConfidence: partial.jobId ? 90 : null,
    lastMessageAt: new Date().toISOString(),
    unreadCount: 0,
    snippet: 'Thanks for applying.',
    participants: ['maya@acme.test', 'local-user@ajas.dev'],
    ...partial,
  }
}

let threads: EmailThread[] = [
  thread({
    id: 't-staff',
    subject: 'Staff Engineer at Acme (JOB-SE-1)',
    jobId: 'job-staff',
    jobTitle: 'Staff Engineer',
    jobCompany: 'Acme',
    linked: true,
    snippet: 'Are you open to a screen this week?',
  }),
  thread({
    id: 't-open',
    subject: 'Thanks for applying',
    unreadCount: 1,
    snippet: 'We received your application.',
    participants: ['noreply@careers-unknown.test', 'local-user@ajas.dev'],
  }),
]

const messages: Record<string, EmailMessage[]> = {
  't-staff': [
    {
      id: 'm1',
      threadId: 't-staff',
      from: { address: 'maya@acme.test', name: 'Maya Chen' },
      to: ['local-user@ajas.dev'],
      cc: [],
      subject: 'Staff Engineer at Acme (JOB-SE-1)',
      bodyText: 'Hi — we would like to talk about the Staff Engineer role at Acme. Are you open to a screen this week?',
      receivedAt: new Date(Date.now() - 86_400_000).toISOString(),
      isIncoming: true,
      isRead: true,
      deliveryStatus: 'received',
      hasAttachments: false,
      attachments: [],
    },
  ],
  't-open': [
    {
      id: 'm2',
      threadId: 't-open',
      from: { address: 'noreply@careers-unknown.test', name: 'Talent Team' },
      to: ['local-user@ajas.dev'],
      cc: [],
      subject: 'Thanks for applying',
      bodyText: 'We received your application and will be in touch if there is a fit.',
      receivedAt: new Date().toISOString(),
      isIncoming: true,
      isRead: false,
      deliveryStatus: 'received',
      hasAttachments: false,
      attachments: [],
    },
  ],
}

export const mockEmailApi: EmailApi = {
  async status() {
    return mailbox
  },
  async listThreads(query = {}) {
    let items = threads
    if (query.jobId) items = items.filter((row) => row.jobId === query.jobId)
    if (query.unlinked) items = items.filter((row) => !row.linked)
    return { items, nextCursor: null, total: items.length }
  },
  async listJobThreads(jobId) {
    return mockEmailApi.listThreads({ jobId })
  },
  async listMessages(threadId) {
    const row = threads.find((item) => item.id === threadId)
    if (!row) throw new Error('Thread not found')
    row.unreadCount = 0
    const items = messages[threadId] || []
    items.forEach((item) => {
      item.isRead = true
    })
    mailbox.unreadCount = threads.reduce((sum, item) => sum + item.unreadCount, 0)
    return { thread: row, items, nextCursor: null, total: items.length }
  },
  async reply(threadId, body) {
    if (!body.bodyText.trim()) throw new Error('bodyText is required')
    const item: EmailMessage = {
      id: `sent-${Date.now()}`,
      threadId,
      from: { address: mailbox.address || 'you@ajas.dev', name: 'You' },
      to: ['maya@acme.test'],
      cc: [],
      subject: 'Re: thread',
      bodyText: body.bodyText,
      receivedAt: new Date().toISOString(),
      sentAt: new Date().toISOString(),
      isIncoming: false,
      isRead: true,
      deliveryStatus: 'sent',
      hasAttachments: false,
      attachments: [],
    }
    messages[threadId] = [...(messages[threadId] || []), item]
    return item
  },
  async suggestions() {
    return [
      { text: 'Thanks, I can talk this week.', tone: 'professional', rationale: 'Offers times.' },
      { text: 'Thanks — when works?', tone: 'concise', rationale: 'Short.' },
      { text: 'Really appreciate the note, happy to chat.', tone: 'warm', rationale: 'Friendly.' },
    ]
  },
  async refresh() {
    mailbox.lastSyncedAt = new Date().toISOString()
    return { status: 'ok', ...mailbox }
  },
  async templates() {
    return templates
  },
  async link(threadId, jobId) {
    const row = threads.find((item) => item.id === threadId)
    if (!row) throw new Error('Thread not found')
    row.jobId = jobId
    row.linked = true
    row.linkSource = 'manual'
    row.jobTitle = 'Staff Engineer'
    row.jobCompany = 'Acme'
    return row
  },
  async unlink(threadId) {
    const row = threads.find((item) => item.id === threadId)
    if (!row) throw new Error('Thread not found')
    row.jobId = null
    row.linked = false
    row.linkSource = null
    row.jobTitle = null
    row.jobCompany = null
    return row
  },
}
