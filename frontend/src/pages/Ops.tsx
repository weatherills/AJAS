import { useEffect, useState } from 'react'
import { AppNav } from '../components/AppNav'
import { chartBars } from '../lib/metrics'
import { digestCopy, notificationInbox, pushNotification, type AppNotification } from '../lib/notifications'
import { json, request, setUserId } from '../api/live'

type Slo = { route: string; budgetMs: number; p95Ms: number | null; samples: number; ok: boolean }
type Trace = { traceId: string; name: string; elapsedMs: number; ok: boolean }
type Drift = { precision: number; baseline: number; delta: number; alert: boolean; period: string }

export function OpsPage() {
  const [role, setRole] = useState<string | null>(null)
  const [slo, setSlo] = useState<Slo[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [drift, setDrift] = useState<Drift | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [traceError, setTraceError] = useState<string | null>(null)
  const [notes, setNotes] = useState<AppNotification[]>(() => notificationInbox())
  const [digest, setDigest] = useState(() => digestCopy())
  const [auditActor, setAuditActor] = useState('')
  const [auditAction, setAuditAction] = useState('')
  const [auditRows] = useState<AuditRow[]>([
    { at: '2026-09-13T10:00:00Z', actor: 'ada', action: 'ingest', target: 'job-1' },
    { at: '2026-09-13T12:00:00Z', actor: 'linus', action: 'apply', target: 'job-2' },
  ])

  useEffect(() => {
    void (async () => {
      try {
        const me = await json<{ role: string }>(await request('/api/v1/auth/me'))
        setRole(me.role)
        const sloBody = await json<{ slo: Slo[] }>(await request('/api/v1/ops/slo'))
        setSlo(sloBody.slo)
        const driftBody = await json<Drift>(await request('/api/v1/learning/drift'))
        setDrift(driftBody)
        if (me.role === 'admin') {
          try {
            const traceBody = await json<{ items: Trace[] }>(await request('/api/v1/ops/traces'))
            setTraces(traceBody.items)
            setTraceError(null)
          } catch (err) {
            setTraceError(err instanceof Error ? err.message : 'Could not load traces')
          }
        }
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load ops')
      }
    })()
  }, [])

  return (
    <div className="page library-page ops-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Operations</h1>
          <p className="tagline">Live SLO samples, traces, and learning drift.</p>
        </div>
      </header>
      {error && <p className="inline-error">{error}</p>}
      <section className="editor-section">
        <h2>Role</h2>
        <p>{role || '…'}</p>
        {role && role !== 'admin' && (
          <p className="muted">
            Traces are limited to admins. In Settings, set the user id to <code>local-admin</code> and reload this
            page.
            <button type="button" className="link-btn" onClick={() => { setUserId('local-admin'); window.location.reload() }}>
              Use local-admin
            </button>
          </p>
        )}
      </section>
      <section className="editor-section">
        <h2>Notification center</h2>
        <p className="muted">In-app toasts plus the digest email payload for unread events.</p>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            pushNotification({ kind: 'digest', title: 'Ops ping', body: 'SLO sample recorded.' })
            setNotes(notificationInbox())
            setDigest(digestCopy())
          }}
        >
          Preview toast
        </button>
        <p>{digest}</p>
        <ul>
          {notes.slice(0, 8).map((item) => (
            <li key={item.id}>
              {item.title} — {item.body}
            </li>
          ))}
        </ul>
      </section>
      <section className="editor-section">
        <h2>Audit trail</h2>
        <label>
          Actor
          <input value={auditActor} onChange={(event) => setAuditActor(event.target.value)} aria-label="Filter audit by actor" />
        </label>
        <label>
          Action
          <input value={auditAction} onChange={(event) => setAuditAction(event.target.value)} aria-label="Filter audit by action" />
        </label>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            const csv = auditCsv(filterAudit(auditRows, { actor: auditActor, action: auditAction }))
            const blob = new Blob([csv], { type: 'text/csv' })
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = 'ajas-audit.csv'
            link.click()
            URL.revokeObjectURL(url)
          }}
        >
          Export CSV
        </button>
        <ul>
          {filterAudit(auditRows, { actor: auditActor, action: auditAction }).map((row) => (
            <li key={`${row.at}-${row.actor}-${row.action}`}>
              {row.at} · {row.actor} · {row.action} · {row.target}
            </li>
          ))}
        </ul>
      </section>
      <section className="editor-section">
        <h2>Metrics</h2>
        <p className="muted">Grafana-style counters for ingestion, matching, and apply volume.</p>
        <div className="metrics-chart" role="img" aria-label="Pipeline volume chart">
          {chartBars([
            { name: 'Ingestion', value: 12, color: '#38bdf8' },
            { name: 'Matches', value: 9, color: '#34d399' },
            { name: 'Applies', value: 4, color: '#fbbf24' },
            { name: 'Errors', value: 1, color: '#f87171' },
          ]).map((bar) => (
            <div key={bar.name} className="metrics-col">
              <div className="metrics-bar" style={{ height: bar.height, background: bar.color }} />
              <span>{bar.name}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="editor-section ops-slo">
        <h2>SLOs</h2>
        {slo.length === 0 || slo.every((row) => row.samples === 0) ? (
          <p className="muted">No live samples yet. Open Review or the Job Feed, then reload Ops.</p>
        ) : null}
        <ul>
          {slo.map((row) => (
            <li key={row.route}>
              {row.route} — p95 {row.p95Ms ?? 'n/a'}ms / {row.budgetMs}ms ({row.samples} samples) {row.ok ? 'ok' : 'alert'}
            </li>
          ))}
        </ul>
      </section>
      {drift && (
        <section className="editor-section">
          <h2>Learning drift</h2>
          <p>
            Precision {drift.precision} vs baseline {drift.baseline} (Δ {drift.delta}). {drift.alert ? 'Alert' : 'Within threshold'}.
          </p>
        </section>
      )}
      {role === 'admin' && (
        <section className="editor-section ops-traces">
          <h2>Recent traces</h2>
          {traceError && <p className="inline-error">{traceError}</p>}
          {!traceError && traces.length === 0 && (
            <p className="muted">No traces yet. Rank a job or open Review to record spans.</p>
          )}
          {traces.length > 0 && (
            <ul>
              {traces.map((row) => (
                <li key={row.traceId + row.name}>
                  {row.name} {row.elapsedMs}ms {row.ok ? 'ok' : 'error'}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
