import type { EmailStatus } from '../api/emailTypes'
import { demoMailbox, graphConnected, oauthConfigured } from '../lib/email'

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
  const oauthOk = oauthConfigured(status)
  const heading = !oauthOk
    ? 'Microsoft OAuth is not configured'
    : jobScoped
      ? 'Microsoft 365 is not connected'
      : 'Connect Microsoft 365 Email'
  const copy = !oauthOk
    ? jobScoped
      ? 'This server has no Microsoft Graph app credentials, so live recruiter mail for this job cannot be connected. Open Settings for details.'
      : 'This server has no Microsoft Graph app credentials, so AJAS cannot sign in to Microsoft 365. The demo mailbox is local sample data, not Graph.'
    : jobScoped
      ? 'Live recruiter mail for this job comes from Microsoft Graph. Connect your mailbox in Settings.'
      : 'AJAS reads recruiter mail through Microsoft Graph. Connect your mailbox in Settings.'
  const cta = oauthOk ? 'Connect Microsoft 365' : 'Open Settings'
  return (
    <section
      className={`email-graph-notice ${compact ? 'is-compact' : 'empty-state'}${oauthOk ? '' : ' is-unconfigured'}`}
      aria-labelledby="connect-email"
    >
      <h2 id="connect-email">{heading}</h2>
      <p className="muted">{copy}</p>
      <a className="primary" href="#/settings">
        {cta}
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
