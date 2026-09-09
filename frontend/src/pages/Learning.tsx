import { useCallback, useEffect, useState } from 'react'
import { learningApi, USE_MOCK } from '../api'
import type { LearningMetrics, LearningParams } from '../api/learningTypes'
import { asStrictness, loadPeriod, percent, savePeriod, STRICTNESS_HELP, STRICTNESS_LABEL } from '../lib/learning'

export function LearningPanel({ compact = false }: { compact?: boolean }) {
  const [metrics, setMetrics] = useState<LearningMetrics | null>(null)
  const [params, setParams] = useState<LearningParams | null>(null)
  const [period, setPeriod] = useState<'7d' | '30d'>(loadPeriod)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [nextMetrics, nextParams] = await Promise.all([learningApi.metrics(period), learningApi.params()])
      setMetrics(nextMetrics)
      setParams(nextParams)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load learning metrics')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  function setRange(next: '7d' | '30d') {
    setPeriod(next)
    savePeriod(next)
  }

  if (loading) return <p className="skeleton">Loading learning metrics…</p>
  if (error) {
    return (
      <p className="inline-error">
        {error}{' '}
        <button type="button" className="link-btn" onClick={() => void load()}>
          Retry
        </button>
      </p>
    )
  }
  if (!metrics || !params) return null
  const strictness = asStrictness(params.strictness)
  return (
    <section className={`learning-panel ${compact ? 'is-compact' : ''}`} aria-labelledby="learning-metrics-heading">
      <div className="learning-panel-head">
        <h2 id="learning-metrics-heading">Learning</h2>
        <div className="segmented" role="group" aria-label="Metrics range">
          {(['7d', '30d'] as const).map((item) => (
            <button key={item} type="button" className={period === item ? 'is-selected' : ''} onClick={() => setRange(item)}>
              {item}
            </button>
          ))}
        </div>
      </div>
      <p className="sr-only">{metrics.summary}</p>
      {metrics.empty ? (
        <p>
          No learning signals yet. Start by reviewing matches.{' '}
          <a href="#/review">Open Review</a>
        </p>
      ) : (
        <ul className="metric-grid">
          <li>
            <strong>{percent(metrics.precision_proxy)}</strong>
            <span className="muted">Approve rate ({period})</span>
            {metrics.approveRateDeltaPct != null && (
              <span className="muted">
                {metrics.approveRateDeltaPct >= 0 ? '+' : ''}
                {metrics.approveRateDeltaPct}% vs prior {period}
              </span>
            )}
          </li>
          <li>
            <strong>{metrics.decisions}</strong>
            <span className="muted">Decisions ({period})</span>
          </li>
          <li>
            <strong>{STRICTNESS_LABEL[strictness]}</strong>
            <span className="muted">
              {params.tuningMode === 'auto' ? 'Auto' : 'Manual'} · {percent(params.score_threshold)} threshold
            </span>
          </li>
        </ul>
      )}
      {params.tuningMode === 'auto' && params.sample_size < 5 && (
        <p className="banner">We’ll adapt after your first few choices.</p>
      )}
      {params.tuningMode === 'auto' && params.sample_size >= 5 && (
        <p className="muted">Adjusted from your last {Math.min(params.sample_size, 30)} decisions.</p>
      )}
      <p className="muted">{STRICTNESS_HELP[strictness]}</p>
    </section>
  )
}

export function LearningPage() {
  return (
    <div className="page library-page">
      <header className="library-header">
        <div>
          <a href="#/" className="back-link">
            Home
          </a>
          <h1>Learning Loop</h1>
          <p className="tagline">Approve and reject matches to tune ranking. Metrics stay per-user.</p>
        </div>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API).</p>}
      <LearningPanel />
      <p>
        Decisions are recorded from <a href="#/review">Review</a>. Tuning mode lives in <a href="#/settings">Settings</a>.
      </p>
    </div>
  )
}
