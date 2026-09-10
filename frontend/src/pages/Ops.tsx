import { useEffect, useState } from 'react'
import { AppNav } from '../components/AppNav'
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
