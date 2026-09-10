import { useEffect, useState } from 'react'
import { AppNav } from '../components/AppNav'
import { json, request } from '../api/live'

type Slo = { route: string; budgetMs: number; p95Ms: number | null; samples: number; ok: boolean }
type Trace = { traceId: string; name: string; elapsedMs: number; ok: boolean }
type Drift = { precision: number; baseline: number; delta: number; alert: boolean; period: string }

export function OpsPage() {
  const [role, setRole] = useState<string | null>(null)
  const [slo, setSlo] = useState<Slo[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [drift, setDrift] = useState<Drift | null>(null)
  const [error, setError] = useState<string | null>(null)

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
          const traceBody = await json<{ items: Trace[] }>(await request('/api/v1/ops/traces'))
          setTraces(traceBody.items)
        }
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load ops')
      }
    })()
  }, [])

  return (
    <div className="page library-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Operations</h1>
          <p className="tagline">SLO budgets, traces, and learning drift. Admin traces require X-Role: admin.</p>
        </div>
      </header>
      {error && <p className="inline-error">{error}</p>}
      <section className="editor-section">
        <h2>Role</h2>
        <p>{role || '…'}</p>
      </section>
      <section className="editor-section">
        <h2>SLOs</h2>
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
      {traces.length > 0 && (
        <section className="editor-section">
          <h2>Recent traces</h2>
          <ul>
            {traces.map((row) => (
              <li key={row.traceId + row.name}>
                {row.name} {row.elapsedMs}ms {row.ok ? 'ok' : 'error'}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
