import type { UiStatus } from '../lib/status'

const LABELS: Record<UiStatus, string> = {
  Queued: 'Queued',
  Parsing: 'Parsing',
  Ready: 'Ready',
  'Needs review': 'Needs review',
  Failed: 'Failed',
}

export function StatusBadge({ status }: { status: UiStatus }) {
  const slug = status.toLowerCase().replace(/\s+/g, '-')
  return (
    <span className={`status-badge status-${slug}`} aria-label={`Status: ${LABELS[status]}`}>
      {LABELS[status]}
    </span>
  )
}
