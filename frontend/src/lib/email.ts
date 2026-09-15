import type { EmailStatus } from '../api/emailTypes'

export const TEMPLATE_VARS = ['firstName', 'company', 'role', 'jobRef'] as const
export type TemplateVars = (typeof TEMPLATE_VARS)[number]

export function graphConnected(status: EmailStatus | null | undefined): boolean {
  if (!status) return false
  if (typeof status.graphConnected === 'boolean') return status.graphConnected
  return status.connected && !status.demo
}

export function demoMailbox(status: EmailStatus | null | undefined): boolean {
  return Boolean(status?.demo && !graphConnected(status))
}

export function mailboxReadable(status: EmailStatus | null | undefined): boolean {
  return graphConnected(status) || demoMailbox(status)
}

export function oauthConfigured(status: EmailStatus | null | undefined): boolean {
  if (!status) return true
  return status.oauthConfigured !== false
}

const TOKEN = /\{(firstName|company|role|jobRef)\}/g

export function fillTemplate(text: string, values: Partial<Record<TemplateVars, string>>): string {
  return text.replace(TOKEN, (_, key: TemplateVars) => values[key] || `{${key}}`)
}

export function leftoverVars(text: string): TemplateVars[] {
  return Array.from(new Set(Array.from(text.matchAll(TOKEN), (match) => match[1] as TemplateVars))).sort()
}

export function relativeTime(stamp: string, now = Date.now()): string {
  const then = new Date(stamp).getTime()
  if (Number.isNaN(then)) return stamp
  const delta = Math.max(0, now - then)
  const minutes = Math.round(delta / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(stamp).toLocaleDateString()
}

export function formatWhen(stamp: string | null | undefined): string {
  if (!stamp) return 'Never'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return date.toLocaleString()
}

export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MAX_MESSAGE_BYTES = 25 * 1024 * 1024
export const MAX_FILES = 20

export type AttachmentReject = { name: string; reason: string }

export function validateAttachments(
  incoming: File[],
  existing: File[] = [],
): { accepted: File[]; rejected: AttachmentReject[]; error: string | null } {
  const accepted = [...existing]
  const rejected: AttachmentReject[] = []
  let total = accepted.reduce((sum, file) => sum + file.size, 0)
  for (const file of incoming) {
    if (accepted.length >= MAX_FILES) {
      rejected.push({ name: file.name, reason: 'You can attach at most 20 files.' })
      continue
    }
    if (file.size > MAX_FILE_BYTES) {
      rejected.push({ name: file.name, reason: `${file.name} is over 10 MB.` })
      continue
    }
    if (total + file.size > MAX_MESSAGE_BYTES) {
      rejected.push({ name: file.name, reason: `${file.name} would exceed the 25 MB attachment limit.` })
      continue
    }
    accepted.push(file)
    total += file.size
  }
  return { accepted, rejected, error: rejected[0]?.reason || null }
}

export function insertAtCaret(source: string, insert: string, start: number, end: number): { text: string; caret: number } {
  const from = Math.max(0, Math.min(start, source.length))
  const to = Math.max(from, Math.min(end, source.length))
  return { text: source.slice(0, from) + insert + source.slice(to), caret: from + insert.length }
}

export function htmlToPlain(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function plainToHtml(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return `<p>${escaped.replace(/\n/g, '<br>')}</p>`
}

export function sanitizeMailHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/javascript:/gi, '')
}

export function needsSendConfirm(opts: { to: string[]; cc: string[]; subject: string }): boolean {
  const recipients = [...opts.to, ...opts.cc].map((item) => item.trim()).filter(Boolean)
  return recipients.length > 1 || !opts.subject.trim()
}

export function attachmentKind(contentType: string, name: string): 'pdf' | 'image' | 'file' {
  const type = contentType.toLowerCase()
  const lower = name.toLowerCase()
  if (type.startsWith('image/') || /\.(png|jpe?g|gif|webp)$/.test(lower)) return 'image'
  if (type === 'application/pdf' || lower.endsWith('.pdf')) return 'pdf'
  return 'file'
}

export function attachmentKindLabel(kind: 'pdf' | 'image' | 'file'): string {
  if (kind === 'pdf') return 'PDF'
  if (kind === 'image') return 'Image'
  return 'File'
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function previewable(contentType: string, name: string): boolean {
  const type = contentType.toLowerCase()
  const lower = name.toLowerCase()
  return type.startsWith('image/') || type === 'application/pdf' || /\.(png|jpe?g|pdf)$/.test(lower)
}

export function attachmentNeedsAuthFetch(url: string | null | undefined): boolean {
  if (!url) return false
  return url.startsWith('/api/') || url.startsWith('api/')
}

export function threadVariables(thread: {
  jobTitle: string | null
  jobCompany: string | null
  participants: string[]
}): Partial<Record<TemplateVars, string>> {
  const recruiter = thread.participants.find((item) => !item.includes('ajas.dev')) || ''
  const firstName = recruiter.split('@')[0]?.split('.')[0] || 'there'
  return {
    firstName: firstName.charAt(0).toUpperCase() + firstName.slice(1),
    company: thread.jobCompany || '',
    role: thread.jobTitle || '',
    jobRef: thread.jobTitle ? thread.jobTitle.replace(/\s+/g, '-').toUpperCase() : '',
  }
}
