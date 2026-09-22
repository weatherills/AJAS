import { useCallback, useEffect, useMemo, useState } from 'react'
import { USE_MOCK, autoApplyApi } from '../api'
import { seedMockApplyStatuses } from '../api/autoApplyMock'
import type { ApplyDetail, ApplySummary, JobSource } from '../api/autoApplyTypes'
import { AppNav } from '../components/AppNav'
import { JobCrossLinks } from '../components/JobCrossLinks'
import { JobEmailsTab } from '../components/JobEmailsTab'
import { ToastStack } from '../components/Toast'
import {
  canCancel,
  canMarkManualSubmitted,
  copyAnswersText,
  effectiveApplyState,
  isInFlight,
  matchesStatusFilter,
  sourceBadge,
  stateLabel,
} from '../lib/autoApply'
import { manualPackageSteps } from '../lib/sprint15Kanban'
import { applyHref, reviewHref, useHashSearch } from '../lib/routes'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }
type StatusFilter = 'all' | 'queued' | 'submitted' | 'needs_action' | 'failed'

function rowState(row: { state: string; state_history?: ApplyDetail['state_history'] }): string {
  return effectiveApplyState(row.state, row.state_history)
}

export function ApplyPage({ requestId }: { requestId: string | null }) {
  const search = useHashSearch()
  const jobFilter = search.get('job')
  const [items, setItems] = useState<ApplySummary[]>([])
  const [detail, setDetail] = useState<ApplyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [busy, setBusy] = useState(false)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [logsOpen, setLogsOpen] = useState(false)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (USE_MOCK) seedMockApplyStatuses()
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

  useEffect(() => {
    if (!detail || !isInFlight(detail.state)) return
    const timer = window.setInterval(() => {
      void autoApplyApi
        .get(detail.request_id)
        .then((next) => {
          setDetail(next)
          setItems((prev) =>
            prev.map((row) =>
              row.request_id === next.request_id ? { ...row, state: next.state, updated_at: next.updated_at } : row,
            ),
          )
        })
        .catch(() => undefined)
    }, 1500)
    return () => window.clearInterval(timer)
  }, [detail])

  const jobId = detail?.source.job_posting_id || jobFilter
  const listed = useMemo(() => {
    const scoped = jobFilter ? items.filter((row) => row.job_id === jobFilter) : items
    return scoped.filter((row) => matchesStatusFilter(rowState(row), statusFilter))
  }, [items, jobFilter, statusFilter])

  useEffect(() => {
    if (requestId || loading || !jobFilter) return
    const match = items.find((row) => row.job_id === jobFilter)
    if (!match) return
    const href = applyHref(match.request_id, jobFilter)
    if (window.location.hash !== href) window.location.hash = href
  }, [requestId, loading, jobFilter, items])

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

  const markSubmitted = async () => {
    if (!detail || !canMarkManualSubmitted(detail.state)) return
    setBusy(true)
    try {
      await autoApplyApi.markManualSubmitted(detail.request_id)
      toast('Marked as manually submitted')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not mark submitted', 'error')
    } finally {
      setBusy(false)
    }
  }

  const lastNote = detail?.state_history.length
    ? detail.state_history[detail.state_history.length - 1]
    : null

  return (
    <div className="page library-page apply-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Auto-Apply</h1>
          <p className="tagline">Track Greenhouse and Lever submissions and manual packages from Review.</p>
          {jobId && <JobCrossLinks jobId={jobId} current="apply" />}
        </div>
        <a className="secondary" href={reviewHref({ jobId })}>
          Review queue
        </a>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API). Applications stay in this browser session.</p>}
      {error && <p className="inline-error">{error}</p>}
      {loading && <p className="muted">Loading applications…</p>}
      <div className="apply-layout">
        <section>
          <h2>Applications</h2>
          <div className="apply-filters" role="tablist" aria-label="Filter applications by status">
            {(
              [
                ['all', 'All'],
                ['queued', 'Queued'],
                ['submitted', 'Submitted / Received'],
                ['needs_action', 'Needs Action'],
                ['failed', 'Failed'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={statusFilter === value}
                className={statusFilter === value ? 'review-tab is-active' : 'review-tab'}
                onClick={() => setStatusFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {!loading && listed.length === 0 && (
            <p className="muted">
              {jobFilter
                ? 'No applications for this job yet. Open Review and choose Auto-Apply.'
                : 'No applications yet. Open a match in Review and choose Auto-Apply.'}{' '}
              <a href={reviewHref({ jobId: jobFilter })}>Review</a>
            </p>
          )}
          <ul className="apply-list">
            {listed.map((row) => {
              const badge = sourceBadge((row.vendor as JobSource) || 'greenhouse')
              const shown = rowState(row)
              return (
                <li key={row.request_id}>
                  <a
                    className={row.request_id === requestId ? 'apply-row is-active' : 'apply-row'}
                    href={applyHref(row.request_id, row.job_id)}
                  >
                    <div>
                      <strong>{row.job_id || row.request_id}</strong>
                      <div className="muted">
                        {badge.label} · {row.mode === 'manual_package' ? 'manual' : 'API'}
                      </div>
                    </div>
                    <span className={`status-badge status-${shown}`}>{stateLabel(shown)}</span>
                  </a>
                </li>
              )
            })}
          </ul>
        </section>
        <aside className="apply-detail" aria-live="polite">
          {!requestId && <p className="muted">Select an application to see status, artifacts, and history.</p>}
          {detail && (
            <>
              <h2>Status</h2>
              <p>
                <span className={`status-badge status-${rowState(detail)}`}>{stateLabel(rowState(detail))}</span>
              </p>
              <p className="muted">Request {detail.request_id}</p>
              {lastNote && (
                <p className="muted">
                  Last event {lastNote.event} · {lastNote.at}
                </p>
              )}
              {detail.source.external_application_id && (
                <p>
                  Provider id <code>{detail.source.external_application_id}</code>
                </p>
              )}
              {detail.failure_reason && <p className="inline-error">{detail.failure_reason}</p>}
              {detail.manual_fallback && (
                <section className="apply-manual">
                  <h3>{detail.captcha ? 'Captcha / SSO — finish in the browser' : 'Manual package'}</h3>
                  <p>{detail.manual_next_steps}</p>
                  <ol>
                    {manualPackageSteps(Boolean(detail.captcha)).map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                  {detail.artifacts.deep_link_url && (
                    <p>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          void navigator.clipboard?.writeText(detail.artifacts.deep_link_url || '')
                          toast('Posting URL copied')
                        }}
                      >
                        Copy posting URL
                      </button>
                    </p>
                  )}
                  {detail.cover_letter_text && (
                    <p>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          void navigator.clipboard?.writeText(detail.cover_letter_text || '')
                          toast('Cover letter copied')
                        }}
                      >
                        Copy cover letter
                      </button>
                    </p>
                  )}
                  {detail.autofill.length > 0 && (
                    <p>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          void navigator.clipboard?.writeText(copyAnswersText(detail.autofill))
                          toast('Answers copied')
                        }}
                      >
                        Copy answers
                      </button>
                    </p>
                  )}
                </section>
              )}
              {typeof detail.retry_count === 'number' && detail.retry_count > 0 && (
                <p className="muted">Retries so far: {detail.retry_count} (exponential backoff on 429/5xx)</p>
              )}
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
                {detail.artifacts.cover_letter_blob_sas && (
                  <p>
                    <a href={detail.artifacts.cover_letter_blob_sas}>Cover letter</a>
                  </p>
                )}
              </section>
              {detail.cover_letter_text && (
                <section>
                  <h3>Cover letter{detail.cover_letter_source ? ` (${detail.cover_letter_source})` : ''}</h3>
                  <pre className="apply-cover">{detail.cover_letter_text}</pre>
                </section>
              )}
              <section>
                <h3>Autofill</h3>
                {detail.autofill.map((row) => (
                  <p key={row.field_key}>
                    <strong>{row.field_key}</strong> {row.value}
                  </p>
                ))}
                {detail.vendor_fields && Object.keys(detail.vendor_fields).length > 0 && (
                  <>
                    <h4>Sent to {sourceBadge((detail.source.type as JobSource) || 'greenhouse').label}</h4>
                    {Object.entries(detail.vendor_fields).map(([key, value]) => (
                      <p key={key}>
                        <strong>{key}</strong> {value}
                      </p>
                    ))}
                  </>
                )}
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
                <button type="button" className="secondary" onClick={() => setLogsOpen((open) => !open)}>
                  {logsOpen ? 'Hide logs' : 'View logs'}
                </button>
                {logsOpen && (
                  <pre className="apply-cover" aria-label="Request logs">
                    {JSON.stringify(
                      {
                        request_id: detail.request_id,
                        state: detail.state,
                        last_error: detail.failure_reason,
                        history: detail.state_history,
                      },
                      null,
                      2,
                    )}
                  </pre>
                )}
              </section>
              {canMarkManualSubmitted(detail.state) && (
                <button type="button" className="primary" disabled={busy} onClick={() => void markSubmitted()}>
                  {busy ? 'Saving…' : 'Mark as manually submitted'}
                </button>
              )}
              {canCancel(detail.state) && (
                <button type="button" className="danger" disabled={busy} onClick={() => void cancel()}>
                  {busy ? 'Cancelling…' : 'Cancel request'}
                </button>
              )}
              {jobId && <JobEmailsTab jobId={jobId} />}
            </>
          )}
        </aside>
      </div>
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
    </div>
  )
}
