import type { JobSource } from '../api/autoApplyTypes'

export const APPLY_STATES = [
  'created',
  'queued',
  'submitting',
  'submitted',
  'packaged',
  'failed',
  'cancelled',
  'rate_limited',
] as const

export type ApplyContact = {
  full_name: string
  email: string
  phone: string
  location: string
}

export type VendorPreviewField = { label: string; value: string }

export function inferJobSource(jobId: string | null | undefined, postingUrl: string | null | undefined): JobSource {
  const hay = `${jobId || ''} ${postingUrl || ''}`.toLowerCase()
  if (hay.includes('lever')) return 'lever'
  if (hay.includes('manual') || hay.includes('captcha') || hay.includes('sso')) return 'manual'
  return 'greenhouse'
}

export function defaultPostingUrl(jobId: string, source: JobSource): string {
  if (source === 'lever') return `https://jobs.lever.co/demo/${encodeURIComponent(jobId)}`
  if (source === 'manual') return `https://jobs.example.com/${encodeURIComponent(jobId)}?unsupported=1`
  return `https://boards.greenhouse.io/demo/jobs/${encodeURIComponent(jobId)}`
}

export function sourceBadge(source: JobSource): { label: string; programmatic: boolean } {
  if (source === 'lever') return { label: 'Lever', programmatic: true }
  if (source === 'greenhouse') return { label: 'Greenhouse', programmatic: true }
  return { label: 'Manual', programmatic: false }
}

export function stateLabel(state: string): string {
  if (state === 'created' || state === 'draft') return 'Draft'
  if (state === 'queued') return 'Queued'
  if (state === 'submitting') return 'Submitting'
  if (state === 'submitted') return 'Submitted'
  if (state === 'packaged' || state === 'needs_review') return 'Needs Action'
  if (state === 'failed') return 'Failed'
  if (state === 'cancelled') return 'Cancelled'
  if (state === 'rate_limited') return 'Rate limited'
  if (state === 'duplicate') return 'Duplicate Detected'
  return state.replace(/_/g, ' ').replace(/^\w/, (ch) => ch.toUpperCase())
}

export function canCancel(state: string): boolean {
  return state === 'queued' || state === 'created'
}

export function canMarkManualSubmitted(state: string): boolean {
  return state === 'packaged' || state === 'needs_review'
}

export function isInFlight(state: string): boolean {
  return state === 'queued' || state === 'submitting' || state === 'created' || state === 'rate_limited'
}

export function splitName(fullName: string): { first: string; last: string } {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return { first: 'Applicant', last: 'Unknown' }
  if (parts.length === 1) return { first: parts[0], last: 'Applicant' }
  return { first: parts[0], last: parts.slice(1).join(' ') }
}

export function vendorFieldPreview(source: JobSource, contact: ApplyContact): VendorPreviewField[] {
  if (source === 'lever') {
    return [
      { label: 'name', value: contact.full_name },
      { label: 'email', value: contact.email },
      { label: 'phone', value: contact.phone },
      { label: 'location', value: contact.location },
    ]
  }
  if (source === 'greenhouse') {
    const { first, last } = splitName(contact.full_name)
    return [
      { label: 'first_name', value: first },
      { label: 'last_name', value: last },
      { label: 'email', value: contact.email },
      { label: 'phone', value: contact.phone },
      { label: 'location', value: contact.location },
    ]
  }
  return [
    { label: 'full_name', value: contact.full_name },
    { label: 'email', value: contact.email },
    { label: 'phone', value: contact.phone },
    { label: 'location', value: contact.location },
  ]
}

export function previewCoverLetter(input: {
  name: string
  jobTitle: string
  company: string
  source: JobSource
  postingUrl?: string | null
}): string {
  const posting = input.postingUrl || `the ${input.source} posting`
  return (
    `Dear hiring team,\n\n` +
    `I am writing to apply for ${input.jobTitle} at ${input.company} (${posting}).` +
    ` My background matches the posting, and I would welcome the chance to contribute.\n\n` +
    `Sincerely,\n${input.name}\n`
  )
}

export function copyAnswersText(
  rows: { field_key?: string; label?: string; value: string }[],
): string {
  return rows
    .map((row) => `${row.label || row.field_key}: ${row.value}`)
    .join('\n')
}

export function autoApplyDisabledReason(opts: { resumeId?: string | null; jobId?: string | null }): string | null {
  if (!opts.resumeId) return 'Upload a resume before Auto-Apply.'
  if (!opts.jobId) return 'This posting is missing job metadata, so Auto-Apply is unavailable.'
  return null
}

const APPLIED_STATES = new Set(['queued', 'submitting', 'submitted', 'packaged', 'rate_limited', 'created'])

export function appliedJobIds(items: { job_id: string | null; state: string }[]): string[] {
  return items.filter((item) => item.job_id && APPLIED_STATES.has(item.state)).map((item) => item.job_id as string)
}
