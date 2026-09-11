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

export function validateAttachments(files: File[]): { accepted: File[]; error: string | null } {
  if (files.length > MAX_FILES) return { accepted: [], error: 'You can attach at most 20 files.' }
  const accepted: File[] = []
  let total = 0
  for (const file of files) {
    if (file.size > MAX_FILE_BYTES) return { accepted: [], error: `${file.name} is over 10 MB.` }
    total += file.size
    if (total > MAX_MESSAGE_BYTES) return { accepted: [], error: 'Attachments exceed 25 MB.' }
    accepted.push(file)
  }
  return { accepted, error: null }
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
