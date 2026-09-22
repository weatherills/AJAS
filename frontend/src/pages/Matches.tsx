import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { matchingApi } from '../api'
import type { MatchRecord, MatchRecordDetail } from '../api/matchingTypes'
import { AppNav } from '../components/AppNav'
import { displayScore, scoreBand, scoreLabel } from '../lib/matching'
import { jobHref, matchesHref, parseHash, reviewHref, useHashSearch } from '../lib/routes'

function scoreClass(score: number) {
  return `review-score review-score-${scoreBand(score)}`
}

export function MatchesPage() {
  const search = useHashSearch()
  const selectedId = search.get('match')
  const [items, setItems] = useState<MatchRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState(() => parseHash(window.location.hash).params.get('job') || '')
  const [resumeId, setResumeId] = useState(() => parseHash(window.location.hash).params.get('resume') || '')
  const [minScore, setMinScore] = useState(() => parseHash(window.location.hash).params.get('min') || '')
  const [detail, setDetail] = useState<MatchRecordDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [rescoring, setRescoring] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await matchingApi.listRecords({
        jobId: jobId || undefined,
        resumeId: resumeId || undefined,
      })
      setItems(rows)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load match records')
    } finally {
      setLoading(false)
    }
  }, [jobId, resumeId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    void (async () => {
      try {
        setDetail(await matchingApi.getRecord(selectedId))
        setDetailError(null)
      } catch (err) {
        setDetail(null)
        setDetailError(err instanceof Error ? err.message : 'Could not load match')
      }
    })()
  }, [selectedId])

  const visible = useMemo(() => {
    const min = minScore ? Number(minScore) : 0
    return items.filter((row) => row.score >= min).sort((a, b) => b.score - a.score)
  }, [items, minScore])

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    window.location.hash = matchesHref({
      jobId: jobId || null,
      resumeId: resumeId || null,
      min: minScore ? Number(minScore) : null,
      matchId: selectedId,
    })
    void load()
  }

  async function rescore() {
    if (!selectedId) return
    setRescoring(true)
    try {
      const saved = await matchingApi.rescore(selectedId)
      setDetail((current) => (current ? { ...current, record: saved.record } : current))
      await load()
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Rescore failed')
    } finally {
      setRescoring(false)
    }
  }

  return (
    <div className="page library-page matches-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Matches</h1>
          <p className="tagline">Persisted scores, evidence, and re-score. Review still owns approve/reject.</p>
        </div>
      </header>
      <form className="matches-filters" onSubmit={applyFilters}>
        <label>
          Job id
          <input value={jobId} onChange={(event) => setJobId(event.target.value)} />
        </label>
        <label>
          Resume id
          <input value={resumeId} onChange={(event) => setResumeId(event.target.value)} />
        </label>
        <label>
          Min score
          <input value={minScore} onChange={(event) => setMinScore(event.target.value)} inputMode="numeric" />
        </label>
        <button type="submit">Filter</button>
      </form>
      {error && (
        <p className="inline-error">
          {error}{' '}
          <button type="button" className="link-btn" onClick={() => void load()}>
            Retry
          </button>
        </p>
      )}
      {loading ? (
        <p className="skeleton">Loading match records…</p>
      ) : visible.length === 0 ? (
        <p>
          No persisted match records yet. Score jobs from the feed, then they show up here.{' '}
          <a href="#/jobs">Open Jobs</a>
        </p>
      ) : (
        <div className="matches-layout">
          <ul className="matches-list">
            {visible.map((row) => (
              <li key={row.id}>
                <a
                  className={row.id === selectedId ? 'is-selected' : undefined}
                  href={matchesHref({ matchId: row.id, jobId: jobId || null, resumeId: resumeId || null, min: minScore ? Number(minScore) : null })}
                >
                  <span className={scoreClass(row.score)}>{displayScore(row.score)}%</span>
                  <span>
                    {row.jobId} · {row.resumeId}
                    <small className="muted"> {scoreLabel(row.score)}</small>
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <section className="matches-detail" aria-live="polite">
            {detailError && <p className="inline-error">{detailError}</p>}
            {!selectedId && <p className="muted">Select a match to see evidence.</p>}
            {detail && (
              <>
                <h2>{detail.record.jobId}</h2>
                <p>
                  Resume <code>{detail.record.resumeId}</code> · model {detail.record.modelVersion || 'matching-v1'}
                </p>
                <p className={scoreClass(detail.record.score)}>{displayScore(detail.record.score)}%</p>
                <ul>
                  {detail.evidence.flatMap((item) => item.sentences).map((sentence) => (
                    <li key={sentence}>{sentence}</li>
                  ))}
                </ul>
                <div className="matches-actions">
                  <button type="button" onClick={() => void rescore()} disabled={rescoring}>
                    {rescoring ? 'Re-scoring…' : 'Re-score'}
                  </button>
                  <a href={reviewHref({ jobId: detail.record.jobId, resumeId: detail.record.resumeId })}>Open in Review</a>
                  <a href={jobHref(detail.record.jobId)}>Open job</a>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
