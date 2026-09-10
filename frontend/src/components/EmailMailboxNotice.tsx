import type { EmailStatus } from '../api/emailTypes'
import { demoMailbox, graphConnected } from '../lib/email'

export function EmailMailboxNotice({
  status,
  compact = false,
  jobScoped = false,
}: {
  status: EmailStatus
  compact?: boolean
  jobScoped?: boolean
}) {
  if (graphConnected(status)) return null
  const heading = jobScoped ? 'Microsoft 365 is not connected' : 'Connect Microsoft 365 Email'
  const copy = jobScoped
    ? 'Live recruiter mail for this job comes from Microsoft Graph. Connect your mailbox in Settings.'
    : 'AJAS reads recruiter mail through Microsoft Graph. Connect your mailbox in Settings.'
  return (
    <section
      className={`email-graph-notice ${compact ? 'is-compact' : 'empty-state'}`}
      aria-labelledby="connect-email"
    >
      <h2 id="connect-email">{heading}</h2>
      <p className="muted">{copy}</p>
      <a className="primary" href="#/settings">
        Connect Microsoft 365
      </a>
    </section>
  )
}

export function EmailDemoBanner({ status }: { status: EmailStatus }) {
  if (!demoMailbox(status)) return null
  return (
    <p className="banner email-demo-banner" role="status">
      Local demo mailbox{status.address ? ` (${status.address})` : ''}. These sample threads are not
      from Microsoft 365.
    </p>
  )
}
