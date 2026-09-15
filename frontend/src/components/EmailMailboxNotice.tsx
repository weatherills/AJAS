import { useState } from 'react'
import type { EmailStatus } from '../api/emailTypes'
import { demoMailbox, graphConnected, oauthConfigured } from '../lib/email'
import { connectMicrosoftMailbox, PopupBlockedError } from '../lib/msOauth'
import { isOAuthNotConfiguredError } from '../lib/settings'

export function EmailMailboxNotice({
  status,
  compact = false,
  jobScoped = false,
  onConnected,
}: {
  status: EmailStatus
  compact?: boolean
  jobScoped?: boolean
  onConnected?: () => void
}) {
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
      ? 'Live recruiter mail for this job comes from Microsoft Graph. Connect your mailbox to pull threads for this posting.'
      : 'AJAS reads recruiter mail through Microsoft Graph. Connect your mailbox to view and reply without leaving the app.'
  const cta = oauthOk ? (connecting ? 'Continue in Microsoft window…' : 'Connect Microsoft 365') : 'Open Settings'

  async function connect() {
    if (!oauthOk) {
      window.location.hash = '#/settings'
      return
    }
    setError(null)
    setConnecting(true)
    try {
      await connectMicrosoftMailbox()
      onConnected?.()
    } catch (err) {
      if (isOAuthNotConfiguredError(err)) {
        window.location.hash = '#/settings'
        return
      }
      setError(err instanceof PopupBlockedError || err instanceof Error ? err.message : 'Could not connect Microsoft 365')
    } finally {
      setConnecting(false)
    }
  }

  return (
    <section
      className={`email-graph-notice ${compact ? 'is-compact' : 'empty-state'}${oauthOk ? '' : ' is-unconfigured'}`}
      aria-labelledby="connect-email"
    >
      <h2 id="connect-email">{heading}</h2>
      <p className="muted">{copy}</p>
      {error && <p className="inline-error">{error}</p>}
      {oauthOk ? (
        <button type="button" className="primary" disabled={connecting} onClick={() => void connect()}>
          {cta}
        </button>
      ) : (
        <a className="primary" href="#/settings">
          {cta}
        </a>
      )}
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
