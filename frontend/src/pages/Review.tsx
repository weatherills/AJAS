import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { reviewApi, USE_MOCK } from '../api'
import type { DecisionValue, ReviewDetail, ReviewFilters, ReviewMatch, ReviewTab } from '../api/reviewTypes'
import { ApplyModal } from '../components/ApplyModal'
import { ToastStack } from '../components/Toast'
import {
  COMMENT_MAX,
  companiesFrom,
  DEFAULT_FILTERS,
  formatDay,
  formatWhen,
  nextAfterRemove,
  PAGE_SIZE,
  statusLabel,
  suggestionLabel,
  truncateText,
  validateComment,
  WHY_MAX,
} from '../lib/review'
import { scoreBand } from '../lib/matching'

type Toast = {
  id: number
  text: string
  tone?: 'info' | 'error'
  actionLabel?: string
  onAction?: () => void
}

function scoreClass(score: number | null) {
  if (score == null) return 'review-score-empty'
  return `review-score review-score-${scoreBand(score)}`
}

export function ReviewPage() {
  const [tab, setTab] = useState<ReviewTab>('matches')
  const [filters, setFilters] = useState<ReviewFilters>(DEFAULT_FILTERS)
  const [items, setItems] = useState<ReviewMatch[]>([])
  const [total, setTotal] = useState(0)
  const [visible, setVisible] = useState(PAGE_SIZE)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [comment, setComment] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [paneError, setPaneError] = useState<string | null>(null)
  const [liveMessage, setLiveMessage] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 1023px)').matches)
  const [applyOpen, setApplyOpen] = useState(false)
  const toastId = useRef(1)
  const commentRef = useRef<HTMLTextAreaElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  const toast = (text: string, tone: Toast['tone'] = 'info', extra?: Pick<Toast, 'actionLabel' | 'onAction'>) => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone, ...extra }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const shown = items.slice(0, visible)
  const companies = useMemo(() => companiesFrom(items), [items])
  const historyMode = tab === 'history'
  const checked = validateComment(comment)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await reviewApi.list(tab, filters)
      setItems(result.items)
      setTotal(result.total)
      setLoadError(null)
      setVisible(PAGE_SIZE)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Could not load the review queue')
    } finally {
      setLoading(false)
    }
  }, [tab, filters])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)')
    const onChange = () => setNarrow(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const openRow = useCallback(async (matchId: string, decisionId?: string) => {
    setSelectedId(matchId)
    setDetailLoading(true)
    setPaneError(null)
    try {
      const next = await reviewApi.get(matchId, decisionId ? { decisionId } : undefined)
      setDetail(next)
      setComment('')
      setCommentError(null)
    } catch (err) {
      setPaneError(err instanceof Error ? err.message : 'Could not load details')
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    if (!items.some((item) => item.matchId === selectedId)) {
      setSelectedId(null)
      setDetail(null)
    }
  }, [items, selectedId])

  const reopenMatch = useCallback(async (matchId: string) => {
    setSaving(true)
    setPaneError(null)
    try {
      const updated = await reviewApi.reopen(matchId)
      toast('Moved back to awaiting decision')
      setLiveMessage(`Reopened ${updated.jobTitle}`)
      await load()
      setTab(updated.source === 'saved' ? 'saved' : 'matches')
      setFilters((prev) => ({ ...prev, status: 'awaiting' }))
      await openRow(updated.matchId)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not reopen this decision.'
      setPaneError(message)
      toast(message, 'error')
    } finally {
      setSaving(false)
    }
  }, [load, openRow])

  const reopen = useCallback(async () => {
    if (!detail) return
    await reopenMatch(detail.match.matchId)
  }, [detail, reopenMatch])

  const decide = useCallback(
    async (decision: DecisionValue) => {
      if (!detail || historyMode) return
      const parsed = validateComment(comment)
      if (parsed.error) {
        setCommentError(parsed.error)
        return
      }
      setSaving(true)
      setPaneError(null)
      const currentId = detail.match.matchId
      try {
        await reviewApi.decide(
          currentId,
          { decision, comment: parsed.value.trim() || undefined },
          { etag: detail.match.etag, idempotencyKey: crypto.randomUUID() },
        )
        toast('Recorded.', 'info', {
          actionLabel: 'Undo',
          onAction: () => void reopenMatch(currentId),
        })
        setLiveMessage(`${statusLabel(decision === 'approve' ? 'approved' : 'rejected')} — ${detail.match.jobTitle}`)
        const remaining = items.filter((item) => item.matchId !== currentId).map((item) => item.matchId)
        const nextId = nextAfterRemove(
          shown.map((item) => item.matchId),
          currentId,
        )
        await load()
        if (narrow) {
          setSelectedId(null)
          setDetail(null)
        } else if (nextId && remaining.includes(nextId)) {
          await openRow(nextId)
        } else {
          setSelectedId(null)
          setDetail(null)
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Could not save decision. Try again.'
        setPaneError(message)
        toast('Could not save decision. Try again.', 'error')
      } finally {
        setSaving(false)
      }
    },
    [comment, detail, historyMode, items, load, narrow, openRow, reopenMatch, shown],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')
      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && target === commentRef.current) {
        event.preventDefault()
        const suggested = detail?.match.suggestion
        void decide(suggested === 'reject' ? 'reject' : 'approve')
        return
      }
      if (typing || !detail || historyMode || saving) return
      if (event.key === 'a' || event.key === 'A') {
        event.preventDefault()
        void decide('approve')
      }
      if (event.key === 'r' || event.key === 'R') {
        event.preventDefault()
        void decide('reject')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [decide, detail, historyMode, saving])

  const emptyCopy =
    tab === 'history'
      ? 'No decisions yet. Approve or reject matches and they will show up here.'
      : tab === 'saved'
        ? 'No saved jobs waiting. Save a posting from the job feed, then decide here.'
        : 'No matches waiting. Scan the job feed or lower the score filter.'

  const paneOpen = Boolean(selectedId)
  const why = truncateText(detail?.match.why, WHY_MAX)
  const suggestion = detail?.match.suggestion || 'none'

  return (
    <div className={`page library-page feed-page review-page ${paneOpen ? 'feed-page-open' : ''}`}>
      <div className="sr-only" aria-live="polite">
        {liveMessage}
      </div>
      <header className="library-header">
        <div>
          <a href="#/" className="back-link">
            Home
          </a>
          <h1>Review &amp; Decision</h1>
          <p className="tagline">Approve or reject matches and saved jobs. Shortcuts: A approve · R reject · ⌘/Ctrl+Enter save with comment.</p>
        </div>
        <div className="feed-header-actions">
          <a className="secondary" href="#/settings">
            Settings
          </a>
          <a className="secondary" href="#/apply">
            Applications
          </a>
          <button type="button" className="secondary feed-filters-toggle" onClick={() => setFiltersOpen(true)}>
            Filters
          </button>
        </div>
      </header>

      {USE_MOCK && <p className="banner">Demo data (mock API). Decisions stay in this browser session.</p>}

      <div className="review-tabs" role="tablist" aria-label="Review queues">
        {(['matches', 'saved', 'history'] as ReviewTab[]).map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? 'review-tab is-active' : 'review-tab'}
            onClick={() => {
              setTab(name)
              setSelectedId(null)
              setDetail(null)
              setFilters({
                ...DEFAULT_FILTERS,
                status: name === 'history' ? 'all' : 'awaiting',
                source: name === 'saved' ? 'saved' : name === 'matches' ? 'ai' : 'all',
              })
            }}
          >
            {name === 'matches' ? 'Matches' : name === 'saved' ? 'Saved' : 'History'}
          </button>
        ))}
      </div>

      <div className="feed-layout review-layout">
        <aside className={`feed-filters ${filtersOpen ? 'is-open' : ''}`} aria-label="Review filters">
          <div className="feed-filters-head">
            <h2>Filters</h2>
            <button type="button" className="secondary feed-filters-toggle" onClick={() => setFiltersOpen(false)}>
              Close
            </button>
          </div>
          <label>
            Score {filters.minScore}–{filters.maxScore}
            <input
              type="range"
              min={0}
              max={100}
              value={filters.minScore}
              aria-label="Minimum score"
              onChange={(event) => setFilters((prev) => ({ ...prev, minScore: Math.min(Number(event.target.value), prev.maxScore) }))}
            />
            <input
              type="range"
              min={0}
              max={100}
              value={filters.maxScore}
              aria-label="Maximum score"
              onChange={(event) => setFilters((prev) => ({ ...prev, maxScore: Math.max(Number(event.target.value), prev.minScore) }))}
            />
          </label>
          <label>
            Company
            <input
              list="review-companies"
              value={filters.company}
              onChange={(event) => setFilters((prev) => ({ ...prev, company: event.target.value }))}
              placeholder="Type a company"
            />
            <datalist id="review-companies">
              {companies.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </label>
          <label>
            Location
            <input
              value={filters.location}
              onChange={(event) => setFilters((prev) => ({ ...prev, location: event.target.value }))}
              placeholder="City or remote"
            />
          </label>
          {tab !== 'saved' && (
            <label>
              Source
              <select
                value={filters.source}
                onChange={(event) => setFilters((prev) => ({ ...prev, source: event.target.value as ReviewFilters['source'] }))}
              >
                <option value="all">All</option>
                <option value="ai">AI</option>
                <option value="saved">Saved</option>
              </select>
            </label>
          )}
          {tab !== 'history' && (
            <label>
              Status
              <select
                value={filters.status}
                onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value as ReviewFilters['status'] }))}
              >
                <option value="awaiting">Awaiting</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="all">All</option>
              </select>
            </label>
          )}
          <label>
            Date added
            <input type="date" value={filters.createdAfter} onChange={(event) => setFilters((prev) => ({ ...prev, createdAfter: event.target.value }))} />
          </label>
          <label>
            Sort
            <select
              value={filters.sort}
              onChange={(event) => setFilters((prev) => ({ ...prev, sort: event.target.value as ReviewFilters['sort'] }))}
            >
              <option value="score">Score</option>
              <option value="date">Date added</option>
              <option value="company">Company</option>
              <option value="title">Title</option>
            </select>
          </label>
        </aside>

        <div className="feed-main" ref={listRef}>
          {loadError && (
            <p className="inline-error">
              {loadError}{' '}
              <button type="button" className="link-btn" onClick={() => void load()}>
                Retry
              </button>
            </p>
          )}
          {loading && <p className="skeleton">Loading queue…</p>}
          {!loading && shown.length === 0 && (
            <div className="empty-state">
              <h2>Nothing here</h2>
              <p className="muted">{emptyCopy}</p>
              <a className="primary" href="#/">
                Back to home
              </a>
            </div>
          )}
          {!loading && shown.length > 0 && (
            <>
              <p className="muted review-count">
                {total} {total === 1 ? 'item' : 'items'}
              </p>
              <div className="review-table-wrap">
                <table className="review-table" aria-label={tab === 'history' ? 'Decision history' : 'Review queue'}>
                  <thead>
                    <tr>
                      <th>Job title</th>
                      <th>Company</th>
                      {historyMode ? (
                        <>
                          <th>Decision</th>
                          <th>Comment</th>
                          <th>Decided</th>
                          <th>Source</th>
                          <th>Score</th>
                        </>
                      ) : (
                        <>
                          <th>Location</th>
                          <th>Source</th>
                          <th>Score</th>
                          <th>Applied?</th>
                          <th>Added</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((item) => {
                      const active = item.matchId === selectedId
                      const commentPreview = truncateText(item.comment, 48)
                      return (
                        <tr key={item.matchId} className={active ? 'is-selected' : undefined}>
                          <td>
                            <button
                              type="button"
                              className="review-row-btn"
                              aria-current={active ? 'true' : undefined}
                              onClick={() => void openRow(item.matchId, historyMode ? item.latestDecisionId || undefined : undefined)}
                            >
                              {item.jobTitle}
                            </button>
                          </td>
                          <td>{item.company}</td>
                          {historyMode ? (
                            <>
                              <td>
                                <span className={`review-status review-status-${item.status}`}>{statusLabel(item.status)}</span>
                              </td>
                              <td title={item.comment || undefined}>{commentPreview.text || '—'}</td>
                              <td>{formatWhen(item.decidedAt)}</td>
                              <td>{item.source === 'ai' ? 'AI' : 'Saved'}</td>
                              <td>
                                <span className={scoreClass(item.scoreAtDecision ?? item.score)}>
                                  {item.scoreAtDecision ?? item.score ?? '—'}
                                </span>
                              </td>
                            </>
                          ) : (
                            <>
                              <td>{item.location}</td>
                              <td>{item.source === 'ai' ? 'AI' : 'Saved'}</td>
                              <td>
                                <span className={scoreClass(item.score)}>{item.score ?? '—'}</span>
                              </td>
                              <td>{item.applied ? 'Y' : 'N'}</td>
                              <td>{formatDay(item.queuedAt)}</td>
                            </>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {visible < total && (
                <button type="button" className="secondary" onClick={() => setVisible((count) => count + PAGE_SIZE)}>
                  Load more
                </button>
              )}
            </>
          )}
        </div>

        {paneOpen && (
          <aside className="job-drawer review-drawer" role="dialog" aria-modal={narrow} aria-labelledby="review-drawer-title">
            <div className="job-drawer-head">
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setSelectedId(null)
                  setDetail(null)
                }}
              >
                Back
              </button>
            </div>
            {detailLoading && <p className="skeleton">Loading details…</p>}
            {paneError && <p className="inline-error">{paneError}</p>}
            {detail && (
              <>
                <header className="review-detail-head">
                  <h2 id="review-drawer-title">{detail.match.jobTitle}</h2>
                  <p className="muted">
                    {detail.match.company} · {detail.match.location}
                  </p>
                  <div className="review-detail-meta">
                    <span className={scoreClass(detail.match.score)}>{detail.match.score ?? '—'}</span>
                    <span className={`review-status review-status-${detail.match.status}`}>{statusLabel(detail.match.status)}</span>
                    {(detail.blobs.jobUrl || detail.match.postingUrl) && (
                      <a className="primary-link" href={detail.blobs.jobUrl || detail.match.postingUrl || '#'} target="_blank" rel="noreferrer">
                        Original posting
                      </a>
                    )}
                  </div>
                </header>
                {detail.snapshotUnavailable && <p className="warn-text">Snapshot unavailable — showing current data.</p>}
                <section>
                  <h3>Summary</h3>
                  {detail.match.highlights?.length ? (
                    <ul>
                      {detail.match.highlights.slice(0, 5).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">{detail.match.summary || 'No summary available yet.'}</p>
                  )}
                  <p>
                    <strong>Why it matches.</strong> {why.text || 'No explanation available yet.'}
                    {why.truncated ? '…' : ''}
                  </p>
                  <p className="muted">Last refreshed {formatWhen(detail.match.updatedAt)}</p>
                </section>
                <section className="review-suggestion">
                  <h3>AI suggestion</h3>
                  <p>{suggestionLabel(suggestion)}</p>
                  {suggestion === 'none' ? (
                    <p className="muted">No suggestion available</p>
                  ) : (
                    <p>{why.text || detail.match.summary}</p>
                  )}
                </section>
                <section>
                  <h3>Resume highlights</h3>
                  {!detail.match.resumeId || !detail.match.resumeHighlights ? (
                    <p className="muted">Resume not found</p>
                  ) : (
                    <>
                      <p>
                        <strong>Matched:</strong> {detail.match.resumeHighlights.matched.join(', ') || '—'}
                      </p>
                      <p>
                        <strong>Missing:</strong> {detail.match.resumeHighlights.missing.join(', ') || '—'}
                      </p>
                      <p>
                        <strong>Experience:</strong> {detail.match.resumeHighlights.years || '—'}
                      </p>
                      <p>
                        <strong>Keywords:</strong> {detail.match.resumeHighlights.keywords.join(', ') || '—'}
                      </p>
                    </>
                  )}
                </section>
                {historyMode ? (
                  <div className="review-actions">
                    <p className="muted">
                      {detail.decision
                        ? `${detail.decision.decision === 'approve' ? 'Approved' : 'Rejected'} ${formatWhen(detail.decision.createdAt)}`
                        : 'Historical decision'}
                    </p>
                    {detail.decision?.comment && <p>{detail.decision.comment}</p>}
                    <div className="review-action-row">
                      <button type="button" className="secondary" disabled={saving} onClick={() => void reopen()}>
                        {saving ? 'Working…' : 'Reopen'}
                      </button>
                      <button type="button" className="primary" onClick={() => setApplyOpen(true)}>
                        Auto-Apply
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="review-actions">
                    <label>
                      Notes
                      <textarea
                        ref={commentRef}
                        value={comment}
                        maxLength={COMMENT_MAX}
                        placeholder="Add notes for your future self (optional)"
                        onChange={(event) => {
                          const parsed = validateComment(event.target.value)
                          setComment(parsed.value)
                          setCommentError(parsed.error)
                        }}
                        disabled={saving}
                      />
                      <span className={checked.remaining < 40 ? 'inline-error' : 'muted'}>
                        {checked.remaining} left
                      </span>
                    </label>
                    {commentError && <p className="inline-error">{commentError}</p>}
                    {paneError && <p className="inline-error">{paneError}</p>}
                    <div className="review-action-row">
                      <button
                        type="button"
                        className="primary"
                        disabled={saving || Boolean(commentError)}
                        title="Approve (A)"
                        onClick={() => void decide('approve')}
                      >
                        {saving ? 'Saving…' : 'Approve'}
                      </button>
                      <button
                        type="button"
                        className="danger"
                        disabled={saving || Boolean(commentError)}
                        title="Reject (R)"
                        onClick={() => void decide('reject')}
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={!detail.match.jobId}
                        title={detail.match.jobId ? 'Submit this posting' : 'Missing job metadata'}
                        onClick={() => setApplyOpen(true)}
                      >
                        Auto-Apply
                      </button>
                    </div>
                    <p className="muted">⌘/Ctrl+Enter saves while the comment box is focused.</p>
                  </div>
                )}
              </>
            )}
          </aside>
        )}
      </div>
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
      {applyOpen && detail && (
        <ApplyModal
          jobTitle={detail.match.jobTitle}
          company={detail.match.company}
          jobId={detail.match.jobId}
          resumeId={detail.match.resumeId}
          postingUrl={detail.match.postingUrl || detail.blobs.jobUrl}
          onClose={() => setApplyOpen(false)}
          onSubmitted={(requestId, state) => {
            setApplyOpen(false)
            toast(`Application ${state}`)
            window.location.hash = `#/apply/${requestId}`
          }}
        />
      )}
    </div>
  )
}
