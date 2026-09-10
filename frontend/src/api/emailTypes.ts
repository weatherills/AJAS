export type EmailStatus = {
  connected: boolean
  graphConnected?: boolean
  address: string | null
  lastSyncedAt: string | null
  unreadCount: number
  demo: boolean
  provider?: 'microsoft365' | 'demo' | null
  lastSyncError?: string | null
  oauthConfigured?: boolean
}

export type EmailThread = {
  id: string
  subject: string
  jobId: string | null
  applicationId?: string | null
  jobTitle: string | null
  jobCompany: string | null
  linked: boolean
  linkSource: string | null
  linkConfidence: number | null
  lastMessageAt: string
  unreadCount: number
  snippet: string
  deliveryAlert?: 'bounced' | 'deferred' | null
  canonical?: boolean
}

export type EmailAttachment = {
  id: string
  fileName: string
  size: number
  contentType: string
  status: string
  skipReason?: string | null
  blobPath?: string | null
}

export type EmailMessage = {
  id: string
  threadId: string
  from: { address: string; name: string }
  to: string[]
  cc: string[]
  subject: string
  bodyText: string
  bodyHtml?: string | null
  receivedAt: string
  sentAt?: string | null
  isIncoming: boolean
  isRead: boolean
  deliveryStatus: string
  hasAttachments: boolean
  attachments: EmailAttachment[]
}

export type EmailSuggestion = {
  text: string
  tone: string
  rationale?: string
}

export type EmailTemplate = {
  id: string
  name: string
  body: string
}

export type ThreadPage = {
  items: EmailThread[]
  nextCursor: string | null
  total: number
}

export type MessagePage = {
  thread: EmailThread
  items: EmailMessage[]
  nextCursor: string | null
  total: number
}

export type ReplyPayload = {
  bodyText: string
  bodyHtml?: string
  templateId?: string
  variables?: Record<string, string>
  attachments?: { fileName: string; contentType: string; size: number; contentBase64?: string }[]
  idempotencyKey?: string
}

export type EmailApi = {
  status(): Promise<EmailStatus>
  listThreads(query?: { jobId?: string; unlinked?: boolean; limit?: number }): Promise<ThreadPage>
  listJobThreads(jobId: string): Promise<ThreadPage>
  listMessages(threadId: string): Promise<MessagePage>
  reply(threadId: string, body: ReplyPayload): Promise<EmailMessage>
  suggestions(threadId: string, body?: { tone?: string; contextNotes?: string }): Promise<EmailSuggestion[]>
  refresh(): Promise<EmailStatus & { status: string }>
  templates(): Promise<EmailTemplate[]>
  previewTemplate(id: string): Promise<{ id: string; name: string; text: string; html: string }>
  link(threadId: string, jobId: string): Promise<EmailThread>
  unlink(threadId: string): Promise<EmailThread>
}
