import { useCallback, useEffect, useState } from 'react'
import { emailApi } from '../api'
import type { EmailStatus, EmailThread } from '../api/emailTypes'
import { EmailThreadPane } from './EmailThreadPane'
import { relativeTime } from '../lib/email'

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
      if (next.connected) {
        const page = await emailApi.listJobThreads(jobId)
        setThreads(page.items)
        setSelectedId((current) => current || page.items[0]?.id || null)
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

  if (loading) return <p className="skeleton">Loading emails…</p>
  if (error) return <p className="inline-error">{error}</p>
  if (status && !status.connected) {
    return (
      <p>
        Connect Microsoft 365 to see emails for this job.{' '}
        <a className="primary-link" href="#/settings">
          Connect Microsoft 365
        </a>
      </p>
    )
  }
  return (
    <div className="job-emails">
      <div className="job-emails-head">
        <h3>Emails</h3>
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
      </div>
      {threads.length === 0 && <p className="muted">No emails yet. Try Refresh.</p>}
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
