import { useCallback, useEffect, useRef, useState } from 'react'
import { emailApi, USE_MOCK } from '../api'
import type { EmailStatus, EmailThread } from '../api/emailTypes'
import { AppNav } from '../components/AppNav'
import { EmailDemoBanner, EmailMailboxNotice } from '../components/EmailMailboxNotice'
import { EmailThreadPane } from '../components/EmailThreadPane'
import { JobCrossLinks } from '../components/JobCrossLinks'
import { ToastStack } from '../components/Toast'
import { demoMailbox, formatWhen, graphConnected, mailboxReadable, relativeTime } from '../lib/email'
import { emailHref, useHashSearch } from '../lib/routes'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function EmailPage() {
  const search = useHashSearch()
  const jobFilter = search.get('job')
  const threadFromHash = search.get('thread')
  const [status, setStatus] = useState<EmailStatus | null>(null)
  const [threads, setThreads] = useState<EmailThread[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(1)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const nextStatus = await emailApi.status()
      setStatus(nextStatus)
      if (mailboxReadable(nextStatus)) {
        const page = await emailApi.listThreads(jobFilter ? { jobId: jobFilter } : undefined)
        setThreads(page.items)
        setSelectedId((current) => {
          if (current && page.items.some((item) => item.id === current)) return current
          return page.items[0]?.id || null
        })
      } else {
        setThreads([])
      }
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load email')
    } finally {
      setLoading(false)
    }
  }, [jobFilter])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!threadFromHash) return
    if (threads.some((item) => item.id === threadFromHash)) setSelectedId(threadFromHash)
  }, [threadFromHash, threads])

  const selected = threads.find((item) => item.id === selectedId) || null
  const graph = graphConnected(status)
  const demo = demoMailbox(status)
  const readable = mailboxReadable(status)

  async function refresh() {
    setSyncing(true)
    try {
      const next = await emailApi.refresh()
      setStatus(next)
      const page = await emailApi.listThreads(jobFilter ? { jobId: jobFilter } : undefined)
      setThreads(page.items)
      toast(graphConnected(next) ? 'Mailbox refreshed' : 'Demo mailbox refreshed')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Refresh failed', 'error')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="page library-page email-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Email</h1>
          <p className="tagline">Recruiter threads linked to tracked jobs, with in-app replies.</p>
          {jobFilter && <JobCrossLinks jobId={jobFilter} current="email" />}
        </div>
        <div className="feed-header-actions">
          {readable && (
            <button type="button" className="primary" disabled={syncing} onClick={() => void refresh()} aria-label="Refresh mailbox">
              {syncing ? 'Syncing…' : 'Refresh'}
            </button>
          )}
        </div>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API).</p>}
      {graph && (
        <p className="muted">
          From: {status?.address} · Last synced {formatWhen(status?.lastSyncedAt)}
          {jobFilter ? ' · Showing threads for this job. ' : ''}
          {jobFilter && (
            <a className="primary-link" href="#/email">
              All threads
            </a>
          )}
        </p>
      )}
      {loading && <p className="skeleton">Loading mailbox…</p>}
      {error && (
        <p className="inline-error">
          {error}{' '}
          <button type="button" className="link-btn" onClick={() => void load()}>
            Retry
          </button>
        </p>
      )}
      {!loading && status && !graph && <EmailMailboxNotice status={status} />}
      {!loading && status && demo && <EmailDemoBanner status={status} />}
      {demo && jobFilter && (
        <p className="muted">
          Showing demo threads for this job.{' '}
          <a className="primary-link" href="#/email">
            All threads
          </a>
        </p>
      )}
      {!loading && graph && threads.length === 0 && (
        <section className="empty-state">
          <p>No emails yet. Try Refresh.</p>
          <button type="button" className="primary" onClick={() => void refresh()}>
            Refresh
          </button>
        </section>
      )}
      {!loading && demo && threads.length === 0 && (
        <p className="muted">No demo emails yet.</p>
      )}
      {readable && threads.length > 0 && (
        <div className="email-layout">
          <nav className="thread-list" aria-label={demo ? 'Demo email threads' : 'Email threads'}>
            {threads.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`thread-item ${item.id === selectedId ? 'is-selected' : ''}`}
                onClick={() => {
                  setSelectedId(item.id)
                  const href = emailHref({ jobId: jobFilter, threadId: item.id })
                  if (window.location.hash !== href) window.location.hash = href
                }}
                aria-current={item.id === selectedId}
              >
                <div className="thread-item-head">
                  <strong>{item.subject}</strong>
                  {item.unreadCount > 0 && <span className="unread-dot" aria-label={`${item.unreadCount} unread`} />}
                </div>
                <p className="muted">{item.snippet}</p>
                <p className="muted">
                  {relativeTime(item.lastMessageAt)}
                  {!item.linked && ' · Unlinked'}
                  {item.linked && item.jobTitle ? ` · ${item.jobTitle}` : ''}
                </p>
              </button>
            ))}
          </nav>
          {selected && (
            <EmailThreadPane
              thread={selected}
              onThreadChange={(next) => {
                setThreads((prev) => prev.map((item) => (item.id === next.id ? next : item)))
              }}
            />
          )}
        </div>
      )}
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
    </div>
  )
}
