import { useCallback, useEffect, useState } from 'react'
import { autoApplyApi, USE_MOCK } from '../api'
import type { ApplyDetail, ApplySummary } from '../api/autoApplyTypes'
import { ToastStack } from '../components/Toast'
import { canCancel, stateLabel } from '../lib/autoApply'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function ApplyPage({ requestId }: { requestId: string | null }) {
  const [items, setItems] = useState<ApplySummary[]>([])
  const [detail, setDetail] = useState<ApplyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [busy, setBusy] = useState(false)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const listed = await autoApplyApi.list()
      setItems(listed.items)
      setError(null)
      if (requestId) {
        setDetail(await autoApplyApi.get(requestId))
      } else {
        setDetail(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load applications')
    } finally {
      setLoading(false)
    }
  }, [requestId])

  useEffect(() => {
    void load()
  }, [load])

  const cancel = async () => {
    if (!detail || !canCancel(detail.state)) return
    setBusy(true)
    try {
      await autoApplyApi.cancel(detail.request_id)
      toast('Application cancelled')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not cancel', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page library-page apply-page">
      <header className="library-header">
        <div>
          <a href="#/" className="back-link">
            Home
          </a>
          <h1>Auto-Apply</h1>
          <p className="tagline">Track programmatic submissions and manual packages from Review.</p>
        </div>
        <a className="secondary" href="#/review">
          Review queue
        </a>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API). Applications stay in this browser session.</p>}
      {error && <p className="inline-error">{error}</p>}
      {loading && <p className="muted">Loading applications…</p>}
      <div className="apply-layout">
        <section>
          <h2>Applications</h2>
          {!loading && items.length === 0 && (
            <p className="muted">
              No applications yet. Open a match in <a href="#/review">Review</a> and choose Auto-Apply.
            </p>
          )}
          <ul className="apply-list">
            {items.map((row) => (
              <li key={row.request_id}>
                <a
                  className={row.request_id === requestId ? 'apply-row is-active' : 'apply-row'}
                  href={`#/apply/${row.request_id}`}
                >
                  <div>
                    <strong>{row.job_id || row.request_id}</strong>
                    <div className="muted">{row.vendor}</div>
                  </div>
                  <span className={`status-badge status-${row.state}`}>{stateLabel(row.state)}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
        <aside className="apply-detail" aria-live="polite">
          {!requestId && <p className="muted">Select an application to see status, artifacts, and history.</p>}
          {detail && (
            <>
              <h2>Status</h2>
              <p>
                <span className={`status-badge status-${detail.state}`}>{stateLabel(detail.state)}</span>
              </p>
              <p className="muted">Request {detail.request_id}</p>
              {detail.source.external_application_id && (
                <p>
                  Provider id <code>{detail.source.external_application_id}</code>
                </p>
              )}
              {detail.failure_reason && <p className="inline-error">{detail.failure_reason}</p>}
              <section>
                <h3>Artifacts</h3>
                {detail.artifacts.package_blob_sas && (
                  <p>
                    <a href={detail.artifacts.package_blob_sas}>Download package</a>
                  </p>
                )}
                {detail.artifacts.deep_link_url && (
                  <p>
                    <a href={detail.artifacts.deep_link_url}>Open posting</a>
                  </p>
                )}
                {detail.artifacts.resume_blob_sas && (
                  <p>
                    <a href={detail.artifacts.resume_blob_sas}>Resume</a>
                  </p>
                )}
              </section>
              <section>
                <h3>Autofill</h3>
                {detail.autofill.map((row) => (
                  <p key={row.field_key}>
                    <strong>{row.field_key}</strong> {row.value}
                  </p>
                ))}
              </section>
              <section>
                <h3>History</h3>
                <ol className="apply-history">
                  {detail.state_history.map((event, index) => (
                    <li key={`${event.event}-${index}`}>
                      {event.event} <span className="muted">{event.at}</span>
                    </li>
                  ))}
                </ol>
              </section>
              {canCancel(detail.state) && (
                <button type="button" className="danger" disabled={busy} onClick={() => void cancel()}>
                  {busy ? 'Cancelling…' : 'Cancel request'}
                </button>
              )}
            </>
          )}
        </aside>
      </div>
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
    </div>
  )
}
