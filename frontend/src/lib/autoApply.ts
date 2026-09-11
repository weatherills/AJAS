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

export function stateLabel(state: string): string {
  if (state === 'rate_limited') return 'Rate limited'
  if (state === 'needs_review') return 'Packaged'
  return state.replace(/_/g, ' ').replace(/^\w/, (ch) => ch.toUpperCase())
}

export function canCancel(state: string): boolean {
  return state === 'queued' || state === 'created'
}

export function canMarkManualSubmitted(state: string): boolean {
  return state === 'packaged' || state === 'needs_review'
}
