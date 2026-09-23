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
  'received',
  'interview_requested',
  'rejected_auto',
  'duplicate',
] as const

/** Backend generation budget is 1000 tokens; UI warns earlier at 400. */
export const COVER_TOKEN_BUDGET = 400
export const COVER_CHAR_BUDGET = 4000
export const COVER_TOKEN_WARN_AT = 320

const LATER_EVENT_TO_STATE: Record<string, string> = {
  vendor_ack: 'received',
  application_received: 'received',
  received: 'received',
  interview_requested: 'interview_requested',
  interview: 'interview_requested',
  vendor_rejected: 'rejected_auto',
  rejected_auto: 'rejected_auto',
  rejected: 'rejected_auto',
  duplicate_detected: 'duplicate',
  duplicate: 'duplicate',
}

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
  if (state === 'received') return 'Received'
  if (state === 'interview_requested') return 'Interview Requested'
  if (state === 'rejected_auto') return 'Rejected (auto)'
  return state.replace(/_/g, ' ').replace(/^\w/, (ch) => ch.toUpperCase())
}

export function effectiveApplyState(
  state: string,
  history?: { event: string; payload?: Record<string, unknown> }[] | null,
): string {
  if (state === 'received' || state === 'interview_requested' || state === 'rejected_auto' || state === 'duplicate') {
    return state
  }
  if (!history?.length) return state
  for (let index = history.length - 1; index >= 0; index -= 1) {
    const event = history[index]
    const payloadType = typeof event.payload?.event_type === 'string' ? event.payload.event_type : ''
    const mapped = LATER_EVENT_TO_STATE[payloadType] || LATER_EVENT_TO_STATE[event.event]
    if (mapped) return mapped
  }
  return state
}

export function matchesStatusFilter(
  state: string,
  filter: 'all' | 'queued' | 'submitted' | 'needs_action' | 'failed',
): boolean {
  if (filter === 'all') return true
  if (filter === 'queued') return state === 'queued' || state === 'created' || state === 'submitting' || state === 'rate_limited'
  if (filter === 'submitted') return state === 'submitted' || state === 'received' || state === 'interview_requested'
  if (filter === 'needs_action') return state === 'packaged' || state === 'needs_review' || state === 'duplicate'
  if (filter === 'failed') return state === 'failed' || state === 'cancelled' || state === 'rejected_auto'
  return true
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

const APPLIED_STATES = new Set([
  'queued',
  'submitting',
  'submitted',
  'packaged',
  'rate_limited',
  'created',
  'received',
  'interview_requested',
  'duplicate',
  'rejected_auto',
])

export function appliedJobIds(items: { job_id: string | null; state: string }[]): string[] {
  return items.filter((item) => item.job_id && APPLIED_STATES.has(item.state)).map((item) => item.job_id as string)
}

export function estimateCoverTokens(text: string): number {
  const trimmed = text.trim()
  if (!trimmed) return 0
  const words = trimmed.split(/\s+/).filter(Boolean).length
  return Math.max(words, Math.ceil(trimmed.length / 4))
}

export function coverUsageWarning(text: string): string | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  const tokens = estimateCoverTokens(trimmed)
  if (trimmed.length > COVER_CHAR_BUDGET) {
    return `Letter is ${trimmed.length} characters (limit ${COVER_CHAR_BUDGET}). Extra text is dropped on submit. You can shorten it or apply without a letter.`
  }
  if (tokens > COVER_TOKEN_BUDGET) {
    return `Letter is about ${tokens} tokens (generation budget ${COVER_TOKEN_BUDGET}). You can shorten it or apply without a letter.`
  }
  if (tokens >= COVER_TOKEN_WARN_AT) {
    return `Letter is about ${tokens} of ${COVER_TOKEN_BUDGET} tokens — near the generation budget. You can still submit.`
  }
  return null
}

export function coverUsageSummary(text: string): string {
  const tokens = estimateCoverTokens(text)
  return `About ${tokens} of ${COVER_TOKEN_BUDGET} tokens used (generation budget).`
}

export type BulkApplyJob = {
  id: string
  title: string
  company: string
  applyUrl?: string | null
}

export function partitionBulkJobs<T extends { id: string; applyUrl?: string | null }>(
  jobs: T[],
  selectedIds: string[],
  opts: { resumeId?: string | null },
): { eligible: T[]; skipped: { job: T; reason: string }[] } {
  const selected = jobs.filter((job) => selectedIds.includes(job.id))
  const eligible: T[] = []
  const skipped: { job: T; reason: string }[] = []
  for (const job of selected) {
    const reason = autoApplyDisabledReason({ resumeId: opts.resumeId, jobId: job.id })
    if (reason) skipped.push({ job, reason })
    else eligible.push(job)
  }
  return { eligible, skipped }
}

export function nextBulkJob<T extends { id: string }>(queue: T[], currentId: string): T | null {
  const index = queue.findIndex((job) => job.id === currentId)
  if (index < 0) return queue[0] || null
  return queue[index + 1] || null
}

export function bulkApplyProgress<T extends { id: string }>(
  queue: T[],
  currentId: string,
): { index: number; total: number; label: string } {
  const total = queue.length
  const found = queue.findIndex((job) => job.id === currentId)
  const index = found < 0 ? 1 : found + 1
  return { index, total, label: total > 1 ? `Job ${index} of ${total}` : '' }
}

export function laterOutcomeFromJob(jobId?: string | null, postingUrl?: string | null): string | null {
  const hay = `${jobId || ''} ${postingUrl || ''}`.toLowerCase()
  if (hay.includes('duplicate') || hay.includes('dup-')) return 'duplicate'
  if (hay.includes('interview')) return 'interview_requested'
  if (hay.includes('reject')) return 'rejected_auto'
  if (hay.includes('received')) return 'received'
  return null
}
