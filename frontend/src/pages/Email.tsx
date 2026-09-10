import { useCallback, useEffect, useRef, useState } from 'react'
import { emailApi, USE_MOCK } from '../api'
import type { EmailStatus, EmailThread } from '../api/emailTypes'
import { AppNav } from '../components/AppNav'
import { EmailThreadPane } from '../components/EmailThreadPane'
import { ToastStack } from '../components/Toast'
import { formatWhen, relativeTime } from '../lib/email'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function EmailPage() {
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
      if (nextStatus.connected) {
        const page = await emailApi.listThreads()
        setThreads(page.items)
        setSelectedId((current) => current || page.items[0]?.id || null)
      } else {
        setThreads([])
      }
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load email')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const selected = threads.find((item) => item.id === selectedId) || null

  async function refresh() {
    setSyncing(true)
    try {
      const next = await emailApi.refresh()
      setStatus(next)
      const page = await emailApi.listThreads()
      setThreads(page.items)
      toast('Mailbox refreshed')
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
        </div>
        <div className="feed-header-actions">
          {status?.connected && (
            <button type="button" className="primary" disabled={syncing} onClick={() => void refresh()} aria-label="Refresh mailbox">
              {syncing ? 'Syncing…' : 'Refresh'}
            </button>
          )}
        </div>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API).</p>}
      {status?.connected && (
        <p className="muted">
          From: {status.address} · Last synced {formatWhen(status.lastSyncedAt)}
          {status.demo ? ' · Local demo mailbox' : ''}
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
      {!loading && status && !status.connected && (
        <section className="empty-state" aria-labelledby="connect-email">
          <h2 id="connect-email">Connect Microsoft 365 Email</h2>
          <p className="muted">AJAS reads recruiter mail for tracked jobs. Connect your mailbox in Settings.</p>
          <a className="primary-link" href="#/settings">
            Connect Microsoft 365
          </a>
        </section>
      )}
      {!loading && status?.connected && threads.length === 0 && (
        <section className="empty-state">
          <p>No emails yet. Try Refresh.</p>
          <button type="button" className="primary" onClick={() => void refresh()}>
            Refresh
          </button>
        </section>
      )}
      {status?.connected && threads.length > 0 && (
        <div className="email-layout">
          <nav className="thread-list" aria-label="Email threads">
            {threads.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`thread-item ${item.id === selectedId ? 'is-selected' : ''}`}
                onClick={() => setSelectedId(item.id)}
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
