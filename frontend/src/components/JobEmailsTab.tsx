import { useCallback, useEffect, useState } from 'react'
import { emailApi } from '../api'
import type { EmailStatus, EmailThread } from '../api/emailTypes'
import { EmailDemoBanner, EmailMailboxNotice } from './EmailMailboxNotice'
import { EmailThreadPane } from './EmailThreadPane'
import { demoMailbox, graphConnected, mailboxReadable, relativeTime } from '../lib/email'

export function JobEmailsTab({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<EmailStatus | null>(null)
  const [threads, setThreads] = useState<EmailThread[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const next = await emailApi.status()
      setStatus(next)
      if (mailboxReadable(next)) {
        const page = await emailApi.listJobThreads(jobId)
        setThreads(page.items)
        setSelectedId((current) => current || page.items[0]?.id || null)
      } else {
        setThreads([])
      }
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load emails')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    void load()
  }, [load])

  const selected = threads.find((item) => item.id === selectedId) || null
  const graph = graphConnected(status)
  const demo = demoMailbox(status)
  const readable = mailboxReadable(status)

  if (loading) return <p className="skeleton">Loading emails…</p>
  if (error) return <p className="inline-error">{error}</p>
  if (status && !readable) {
    return <EmailMailboxNotice status={status} compact jobScoped />
  }

  return (
    <div className="job-emails">
      {status && !graph && <EmailMailboxNotice status={status} compact jobScoped />}
      {status && demo && <EmailDemoBanner status={status} />}
      <div className="job-emails-head">
        <h3>{demo ? 'Demo emails' : 'Emails'}</h3>
        {readable && (
          <button
            type="button"
            className="secondary"
            disabled={syncing}
            onClick={async () => {
              setSyncing(true)
              try {
                await emailApi.refresh()
                await load()
              } finally {
                setSyncing(false)
              }
            }}
          >
            {syncing ? 'Syncing…' : 'Refresh'}
          </button>
        )}
      </div>
      {graph && threads.length === 0 && <p className="muted">No emails yet. Try Refresh.</p>}
      {demo && threads.length === 0 && <p className="muted">No demo emails for this job.</p>}
      <ul className="job-email-threads">
        {threads.map((item) => (
          <li key={item.id}>
            <button type="button" className={item.id === selectedId ? 'is-selected' : ''} onClick={() => setSelectedId(item.id)}>
              {item.subject}
              <span className="muted"> · {relativeTime(item.lastMessageAt)}</span>
              {item.unreadCount > 0 && <span className="unread-dot" />}
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <EmailThreadPane
          compact
          thread={selected}
          onThreadChange={(next) => setThreads((prev) => prev.map((item) => (item.id === next.id ? next : item)))}
        />
      )}
    </div>
  )
}
