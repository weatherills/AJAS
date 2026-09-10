import { useCallback, useEffect, useState } from 'react'
import { AppNav } from '../components/AppNav'
import { learningApi, reviewApi, USE_MOCK } from '../api'
import type { LearningMetrics, LearningParams } from '../api/learningTypes'
import type { ReviewMatch } from '../api/reviewTypes'
import { asStrictness, loadPeriod, percent, savePeriod, STRICTNESS_HELP, STRICTNESS_LABEL } from '../lib/learning'
import { filtersForTab, formatWhen, statusLabel } from '../lib/review'
import { reviewHref } from '../lib/routes'

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
  const historyHref = reviewHref({ tab: 'history' })
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
          <a href={reviewHref()}>Open Review</a>
        </p>
      ) : (
        <ul className="metric-grid">
          <li>
            <a href={historyHref}>
              <strong>{percent(metrics.precision_proxy)}</strong>
              <span className="muted">Approve rate ({period})</span>
              {metrics.approveRateDeltaPct != null && (
                <span className="muted">
                  {metrics.approveRateDeltaPct >= 0 ? '+' : ''}
                  {metrics.approveRateDeltaPct}% vs prior {period}
                </span>
              )}
              {metrics.liftVsBaseline != null && (
                <span className="muted">
                  {metrics.liftVsBaseline >= 0 ? '+' : ''}
                  {metrics.liftVsBaseline} pts vs 50% baseline
                </span>
              )}
            </a>
          </li>
          <li>
            <a href={historyHref}>
              <strong>{metrics.decisions}</strong>
              <span className="muted">Decisions ({period})</span>
            </a>
          </li>
          <li>
            <a href="#/settings">
              <strong>{STRICTNESS_LABEL[strictness]}</strong>
              <span className="muted">
                {params.tuningMode === 'auto' ? 'Auto' : 'Manual'} · {percent(params.score_threshold)} threshold
              </span>
            </a>
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
  const [recent, setRecent] = useState<ReviewMatch[]>([])
  const [recentError, setRecentError] = useState<string | null>(null)

  useEffect(() => {
    void reviewApi
      .list('history', filtersForTab('history'))
      .then((page) => {
        setRecent(page.items.slice(0, 5))
        setRecentError(null)
      })
      .catch((err) => {
        setRecentError(err instanceof Error ? err.message : 'Could not load recent decisions')
      })
  }, [])

  return (
    <div className="page library-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Learning Loop</h1>
          <p className="tagline">Approve and reject matches to tune ranking. Metrics stay per-user.</p>
        </div>
        <a className="secondary" href={reviewHref({ tab: 'history' })}>
          Decision history
        </a>
      </header>
      {USE_MOCK && <p className="banner">Demo data (mock API).</p>}
      <LearningPanel />
      <section className="learning-recent" aria-labelledby="learning-recent-heading">
        <h2 id="learning-recent-heading">Recent decisions</h2>
        {recentError && <p className="inline-error">{recentError}</p>}
        {!recentError && recent.length === 0 && (
          <p className="muted">
            No decisions yet.{' '}
            <a href={reviewHref()}>Open Review</a>
          </p>
        )}
        {recent.length > 0 && (
          <ul className="learning-recent-list">
            {recent.map((item) => (
              <li key={item.matchId}>
                <a href={reviewHref({ matchId: item.matchId, tab: 'history', jobId: item.jobId })}>
                  <strong>{item.jobTitle}</strong>
                  <span className="muted">
                    {item.company} · {statusLabel(item.status)} · {formatWhen(item.decidedAt)}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p>
        Decisions are recorded from <a href={reviewHref()}>Review</a>. Tuning mode lives in <a href="#/settings">Settings</a>.
      </p>
    </div>
  )
}
