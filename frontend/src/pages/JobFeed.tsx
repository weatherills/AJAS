import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { jobsApi, matchingApi, resumeApi, settingsApi, USE_MOCK } from '../api'
import type { JobCard, JobDetail, JobFilters, JobSourceName, SourceStatus } from '../api/jobsTypes'
import type { MatchView } from '../api/matchingTypes'
import { AppNav } from '../components/AppNav'
import { JobCrossLinks } from '../components/JobCrossLinks'
import { JobEmailsTab } from '../components/JobEmailsTab'
import { MatchBadge } from '../components/MatchBadge'
import { MatchMeter } from '../components/MatchMeter'
import { WhyThisScore, WhyThisScoreInline } from '../components/MatchWhy'
import { ToastStack } from '../components/Toast'
import { apiToPercent } from '../lib/settings'
import { jobHaystack, resumeHaystack } from '../lib/matching'
import { jobHref, useHashSearch } from '../lib/routes'
import { preselectReady } from '../lib/status'
import {
  ALL_SOURCES,
  alsoFromLabel,
  backoffRemainingMs,
  defaultFilters,
  formatCountdown,
  formatWhen,
  loadFilters,
  PAGE_SIZE,
  refreshToastForStatuses,
  saveFilters,
  sourceErrorCopy,
  sourceIsConfiguredStatus,
  sourceTitle,
  sourceUnconfiguredCopy as feedSourceUnconfiguredCopy,
  sourcesOffCopy,
  statusLabel,
  takeLastVisit,
} from '../lib/jobs'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

const lastVisit = takeLastVisit()

export function JobFeedPage() {
  const [filters, setFilters] = useState<JobFilters>(() => loadFilters())
  const [items, setItems] = useState<JobCard[]>([])
  const [total, setTotal] = useState(0)
  const [cursor, setCursor] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [statuses, setStatuses] = useState<SourceStatus[]>([])
  const [selected, setSelected] = useState<JobCard | null>(null)
  const [detail, setDetail] = useState<JobDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [offline, setOffline] = useState(!navigator.onLine)
  const [now, setNow] = useState(Date.now())
  const [liveMessage, setLiveMessage] = useState('')
  const [toasts, setToasts] = useState<Toast[]>([])
  const [threshold, setThreshold] = useState(70)
  const [resumeId, setResumeId] = useState<string | null>(null)
  const [resumeText, setResumeText] = useState('')
  const [matches, setMatches] = useState<Record<string, MatchView>>({})
  const [onlyThreshold, setOnlyThreshold] = useState(false)
  const [whyMatch, setWhyMatch] = useState<MatchView | null>(null)
  const [saveOverride, setSaveOverride] = useState<Record<string, boolean>>({})
  const [listMinHeight, setListMinHeight] = useState(0)
  const [drawerTab, setDrawerTab] = useState<'details' | 'emails'>('details')
  const search = useHashSearch()
  const toastId = useRef(1)
  const sentinel = useRef<HTMLDivElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const pollMs = useRef(15_000)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const query = useMemo(
    () => ({
      sources: filters.sources,
      q: filters.q,
      location: filters.location,
      status: filters.status,
      limit: PAGE_SIZE,
      since: lastVisit,
    }),
    [filters],
  )

  const loadPage = useCallback(
    async (nextCursor: string | null, append: boolean) => {
      if (append) setLoadingMore(true)
      else setLoading(true)
      try {
        const result = await jobsApi.list({ ...query, cursor: nextCursor })
        setItems((prev) => (append ? [...prev, ...result.items] : result.items))
        setCursor(result.nextCursor)
        setTotal(result.total)
        setLoadError(null)
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Could not load jobs')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [query],
  )

  const loadStatus = useCallback(async () => {
    try {
      const rows = await jobsApi.sourceStatus()
      setStatuses(rows)
      if (rows.some((item) => item.status === 'syncing')) {
        setLiveMessage('Syncing started')
        pollMs.current = 15_000
      } else {
        pollMs.current = Math.min(60_000, pollMs.current * 1.5 || 15_000)
      }
    } catch {
      /* status bar is non-blocking */
    }
  }, [])

  useEffect(() => {
    saveFilters(filters)
    setPage(1)
    void loadPage(null, false)
  }, [filters, loadPage])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  const selectJob = useCallback(
    (job: JobCard, tab: 'details' | 'emails' = 'details') => {
      setSelected(job)
      setDrawerTab(tab)
      const href = jobHref(job.id, tab)
      if (window.location.hash !== href) window.location.hash = href
    },
    [],
  )

  useEffect(() => {
    const jobId = search.get('job')
    const tab = search.get('tab') === 'emails' ? 'emails' : 'details'
    if (!jobId) return
    if (selected?.id === jobId) {
      if (drawerTab !== tab) setDrawerTab(tab)
      return
    }
    const listed = items.find((item) => item.id === jobId)
    if (listed) {
      setSelected(listed)
      setDrawerTab(tab)
      return
    }
    if (loading) return
    let cancelled = false
    void jobsApi
      .get(jobId)
      .then((detail) => {
        if (cancelled) return
        setSelected(detail)
        setDetail(detail)
        setDrawerTab(tab)
      })
      .catch((err) => {
        if (!cancelled) toast(err instanceof Error ? err.message : 'Job not found', 'error')
      })
    return () => {
      cancelled = true
    }
  }, [search, items, loading, selected?.id, drawerTab])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const doc = await settingsApi.get()
        if (!cancelled) {
          setThreshold(apiToPercent(doc.matchThreshold))
          const sources: JobSourceName[] = []
          if (doc.sources.greenhouseEnabled) sources.push('greenhouse')
          if (doc.sources.leverEnabled) sources.push('lever')
          setFilters((prev) => ({ ...prev, sources }))
        }
      } catch {
        /* keep default 70 */
      }
      try {
        const list = await resumeApi.list()
        const ready = preselectReady(list)
        if (!ready) {
          if (!cancelled) {
            setResumeId(null)
            setResumeText('')
          }
          return
        }
        const detail = await resumeApi.get(ready)
        if (!cancelled) {
          setResumeId(ready)
          setResumeText(resumeHaystack(detail))
        }
      } catch {
        if (!cancelled) setResumeId(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const scoreJobs = useCallback(
    async (jobs: JobCard[]) => {
      if (!jobs.length) {
        setMatches({})
        return
      }
      setMatches((prev) => {
        const next = { ...prev }
        for (const job of jobs) {
          if (!next[job.id]) {
            next[job.id] = {
              jobId: job.id,
              resumeId,
              score: null,
              state: 'loading',
              breakdown: null,
              terms: [],
              explanation: '',
              versions: null,
              computedAt: null,
              persisted: false,
            }
          }
        }
        return next
      })
      try {
        const rows = await matchingApi.scoreMany({
          resumeId,
          resumeText,
          threshold,
          jobs: jobs.map((job) => ({ id: job.id, text: jobHaystack(job) })),
          explanation: true,
        })
        setMatches((prev) => {
          const next = { ...prev }
          for (const row of rows) next[row.jobId] = row
          return next
        })
      } catch (err) {
        setMatches((prev) => {
          const next = { ...prev }
          for (const job of jobs) {
            next[job.id] = {
              jobId: job.id,
              resumeId,
              score: null,
              state: 'error',
              breakdown: null,
              terms: [],
              explanation: '',
              versions: null,
              computedAt: null,
              persisted: false,
              error: err instanceof Error ? err.message : 'Could not compute match',
            }
          }
          return next
        })
      }
    },
    [resumeId, resumeText, threshold],
  )

  const saveMatch = useCallback(
    async (job: JobCard) => {
      if (!resumeId) {
        toast('Upload a resume before saving a match.', 'error')
        return
      }
      try {
        const row = await matchingApi.scoreOne({
          resumeId,
          resumeText,
          threshold,
          job: { id: job.id, text: jobHaystack(job) },
          explanation: true,
          persist: true,
        })
        setMatches((prev) => ({ ...prev, [job.id]: { ...row, persisted: true } }))
        toast('Saved to Review')
      } catch (err) {
        setSaveOverride((prev) => ({ ...prev, [job.id]: false }))
        toast(err instanceof Error ? err.message : 'Could not save this match.', 'error')
      }
    },
    [resumeId, resumeText, threshold],
  )

  useEffect(() => {
    void scoreJobs(items)
  }, [items, scoreJobs])

  useEffect(() => {
    const onOnline = () => {
      setOffline(false)
      toast('Back online. Refreshing…')
      void loadPage(null, false)
      void loadStatus()
    }
    const onOffline = () => {
      setOffline(true)
      toast('You are offline. Showing cached jobs.', 'error')
    }
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [loadPage, loadStatus])

  useEffect(() => {
    const tick = () => setNow(Date.now())
    const handle = window.setInterval(tick, 1000)
    return () => window.clearInterval(handle)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (document.hidden) return
      await loadStatus()
      const limited = statuses.filter(
        (item) => item.status === 'rate_limited' && backoffRemainingMs(item.backoffUntil, Date.now()) === 0,
      )
      for (const row of limited) {
        setLiveMessage('Rate limit ended')
        void refresh(row.source, true)
      }
    }
    const handle = window.setInterval(() => void poll(), pollMs.current)
    return () => window.clearInterval(handle)
  }, [loadStatus, statuses])

  useEffect(() => {
    if (filters.pagination !== 'infinite') return
    const node = sentinel.current
    if (!node) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && cursor && !loadingMore && !loading) {
          void loadPage(cursor, true)
        }
      },
      { root: null, rootMargin: '20% 0px', threshold: 0 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [cursor, filters.pagination, loadPage, loading, loadingMore])

  useEffect(() => {
    if (!selected) {
      setDetail(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    void jobsApi
      .get(selected.id)
      .then((row) => {
        if (!cancelled) setDetail(row)
      })
      .catch(() => {
        if (!cancelled) {
          setDetail({
            ...selected,
            description: selected.snippet,
            descriptionError: 'Could not load full description. Use a source link below.',
          })
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelected(null)
        if (window.location.hash !== '#/jobs') window.location.hash = '#/jobs'
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  async function refresh(source: JobSourceName | 'all', silent = false) {
    if (offline) return
    try {
      const snapshot = await jobsApi.list({ ...query, cursor: null, limit: 500 })
      const before = new Set(snapshot.items.map((item) => item.id))
      setLiveMessage('Syncing started')
      const rows = await jobsApi.refresh(source)
      setStatuses(rows)
      await loadPage(filters.pagination === 'infinite' ? null : String((page - 1) * PAGE_SIZE), false)
      const after = await jobsApi.list({ ...query, cursor: null, limit: 500 })
      const added = after.items.filter((item) => !before.has(item.id)).length
      const outcome = refreshToastForStatuses(source, rows, added)
      if (!silent) toast(outcome.text, outcome.tone)
      setLiveMessage(outcome.live)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Refresh failed', 'error')
      setLiveMessage('Sync error')
      void loadStatus()
    }
  }

  function toggleSource(name: JobSourceName) {
    setFilters((prev) => {
      const on = prev.sources.includes(name)
      const sources = on ? prev.sources.filter((item) => item !== name) : [...prev.sources, name]
      return { ...prev, sources }
    })
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const lever = statuses.find((item) => item.source === 'lever')
  const greenhouse = statuses.find((item) => item.source === 'greenhouse')
  const sourceErrors = statuses.filter((item) => item.status === 'error')
  const sourceUnconfigured = statuses.filter((item) => !sourceIsConfiguredStatus(item))
  const sourcesOff = filters.sources.length === 0 && statuses.some((item) => sourceIsConfiguredStatus(item))

  function sourceBlocked(row: SourceStatus | undefined) {
    return (
      !row ||
      offline ||
      row.status === 'syncing' ||
      row.status === 'unconfigured' ||
      row.configured === false ||
      backoffRemainingMs(row.backoffUntil, now) > 0
    )
  }

  return (
    <div className={`page library-page feed-page ${selected ? 'feed-page-open' : ''}`}>
      <div className="sr-only" aria-live="polite">
        {liveMessage}
      </div>
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Job feed</h1>
          <p className="tagline">Public Greenhouse and Lever postings, merged when they are the same role.</p>
        </div>
        <div className="feed-header-actions">
          <button type="button" className="secondary feed-filters-toggle" onClick={() => setFiltersOpen(true)}>
            Filters
          </button>
          <button
            type="button"
            className="primary"
            disabled={offline || (sourceBlocked(greenhouse) && sourceBlocked(lever))}
            onClick={() => void refresh('all')}
            aria-label="Refresh all sources"
          >
            Refresh all
          </button>
        </div>
      </header>

      {USE_MOCK && <p className="banner">Demo data (mock API). Filters stay in this browser.</p>}
      {offline && <p className="unsaved-banner">Offline — cached jobs only. Refresh is disabled until you reconnect.</p>}
      {sourceUnconfigured.length > 0 && (
        <p className="banner" role="status">
          {sourceUnconfigured.map((item) => feedSourceUnconfiguredCopy(item) || `${sourceTitle(item.source)} is not configured.`).join(' ')}{' '}
          <a href="#/settings">Add a board in Settings</a>
        </p>
      )}
      {sourcesOff && (
        <p className="banner" role="status">
          {sourcesOffCopy()} <a href="#/settings">Open Settings</a>
        </p>
      )}
      {sourceErrors.length > 0 && (
        <p className="unsaved-banner" role="alert">
          {sourceErrors.map((item) => sourceErrorCopy(item) || `${sourceTitle(item.source)} fetch failed.`).join(' ')}
        </p>
      )}

      <div className="feed-status" role="status">
        {(['greenhouse', 'lever'] as JobSourceName[]).map((name) => {
          const row = statuses.find((item) => item.source === name)
          const left = backoffRemainingMs(row?.backoffUntil ?? null, now)
          const blocked = sourceBlocked(row)
          const label = row ? statusLabel(row, now) : 'Idle'
          return (
            <div key={name} className={`feed-source feed-source-${row?.status || 'ok'}`}>
              <div>
                <strong>{sourceTitle(name)}</strong>
                <p className="muted">{label}</p>
                <p className="muted">Last sync {formatWhen(row?.lastSyncAt ?? null)}</p>
                {row?.status === 'error' && (
                  <p className="inline-error" role="alert">
                    {sourceErrorCopy(row) || `${sourceTitle(name)} fetch failed.`}
                  </p>
                )}
                {row && !sourceIsConfiguredStatus(row) && (
                  <p className="muted" role="status">
                    {feedSourceUnconfiguredCopy(row)}{' '}
                    <a href="#/settings">Add a board</a>
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={blocked}
                title={
                  !row || !sourceIsConfiguredStatus(row)
                    ? `${sourceTitle(name)} is not configured`
                    : left > 0
                      ? `Cooling down ${formatCountdown(left)} after a rate limit`
                      : `Refresh ${sourceTitle(name)}`
                }
                aria-label={`Refresh ${sourceTitle(name)}`}
                onClick={() => void refresh(name)}
              >
                {row?.status === 'syncing' ? 'Syncing…' : left > 0 ? formatCountdown(left) : 'Refresh'}
              </button>
            </div>
          )
        })}
      </div>

      <div className="feed-layout">
        <aside className={`feed-filters ${filtersOpen ? 'is-open' : ''}`} aria-label="Filters">
          <div className="feed-filters-head">
            <h2>Filters</h2>
            <button type="button" className="secondary feed-filters-toggle" onClick={() => setFiltersOpen(false)}>
              Close
            </button>
          </div>
          <fieldset>
            <legend>Source</legend>
            {ALL_SOURCES.map((name) => (
              <label key={name} className="chip-toggle">
                <input
                  type="checkbox"
                  checked={filters.sources.includes(name)}
                  onChange={() => toggleSource(name)}
                />
                {sourceTitle(name)}
              </label>
            ))}
          </fieldset>
          <label>
            Search
            <input
              value={filters.q}
              onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
              placeholder="Title, company, or location"
              aria-label="Search jobs"
            />
          </label>
          <label>
            Location
            <input
              value={filters.location}
              onChange={(event) => setFilters((prev) => ({ ...prev, location: event.target.value }))}
              placeholder="Remote, Austin…"
              aria-label="Filter by location"
            />
          </label>
          <label>
            Status
            <select
              value={filters.status}
              onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value as JobFilters['status'] }))}
              aria-label="Filter by new jobs"
            >
              <option value="all">All jobs</option>
              <option value="new">New since last visit</option>
            </select>
          </label>
          <label>
            Pagination
            <select
              value={filters.pagination}
              onChange={(event) =>
                setFilters((prev) => ({ ...prev, pagination: event.target.value as JobFilters['pagination'] }))
              }
              aria-label="Pagination mode"
            >
              <option value="infinite">Infinite scroll</option>
              <option value="pages">Numbered pages</option>
            </select>
          </label>
          <label className="chip-toggle">
            <input
              type="checkbox"
              checked={onlyThreshold}
              onChange={(event) => {
                if (listRef.current) setListMinHeight(listRef.current.scrollHeight)
                setOnlyThreshold(event.target.checked)
              }}
            />
            Only show ≥ threshold ({threshold}%)
          </label>
          <p className="muted">
            Threshold is set in <a href="#/settings">Settings</a>.
          </p>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setFilters(defaultFilters())
              setOnlyThreshold(false)
              setFiltersOpen(false)
            }}
          >
            Clear all
          </button>
        </aside>

        <div className="feed-main" ref={listRef}>
          {loadError && (
            <p className="inline-error">
              {loadError}{' '}
              <button type="button" className="link-btn" onClick={() => void loadPage(null, false)}>
                Retry
              </button>
            </p>
          )}
          {loading && items.length === 0 && (
            <ul className="job-list" aria-hidden="true">
              {Array.from({ length: 4 }).map((_, index) => (
                <li key={index} className="job-card skeleton">
                  Loading jobs
                </li>
              ))}
            </ul>
          )}
          {!loading && items.length === 0 && (
            <div className="empty-state">
              {sourceErrors.length > 0 ? (
                <>
                  <p>Could not refresh job sources</p>
                  {sourceErrors.map((item) => (
                    <p key={item.source} className="muted">
                      {sourceErrorCopy(item)}
                    </p>
                  ))}
                </>
              ) : sourcesOff ? (
                <>
                  <p>Sources are off in Settings</p>
                  <p className="muted">{sourcesOffCopy()}</p>
                  <p className="muted">
                    Turn Greenhouse or Lever on in <a href="#/settings">Settings</a> to see jobs from those boards.
                  </p>
                </>
              ) : sourceUnconfigured.length > 0 ? (
                <>
                  <p>Job sources are not configured</p>
                  {sourceUnconfigured.map((item) => (
                    <p key={item.source} className="muted">
                      {feedSourceUnconfiguredCopy(item)}
                    </p>
                  ))}
                  <p className="muted">
                    Add a Greenhouse board token or Lever company URL in <a href="#/settings">Settings</a>, then enable the source.
                  </p>
                </>
              ) : (
                <>
                  <p>No jobs found</p>
                  <p className="muted">Adjust filters or refresh Greenhouse and Lever.</p>
                </>
              )}
              {sourcesOff || sourceUnconfigured.length > 0 ? (
                <a className="primary" href="#/settings">
                  {sourcesOff ? 'Open Settings' : 'Add a board'}
                </a>
              ) : (
                <button
                  type="button"
                  className="primary"
                  disabled={offline || (sourceBlocked(greenhouse) && sourceBlocked(lever))}
                  onClick={() => void refresh('all')}
                >
                  Retry refresh
                </button>
              )}
            </div>
          )}
          {items.length > 0 && (
            <ul className="job-list" role="list" aria-label="Job postings" style={listMinHeight ? { minHeight: listMinHeight } : undefined}>
              {items.map((job) => {
                const also = alsoFromLabel(job.sources, job.primarySource)
                const match = matches[job.id]
                const hidden = Boolean(
                  onlyThreshold && match?.state === 'computed' && match.score != null && match.score < threshold,
                )
                return (
                  <li key={job.id} className={hidden ? 'job-slot is-filtered' : 'job-slot'}>
                    <div className="job-card">
                      <button type="button" className="job-card-hit" onClick={() => selectJob(job)}>
                        <div className="job-card-top">
                          <h2>{job.title}</h2>
                          <span className={`source-chip source-${job.primarySource}`}>{sourceTitle(job.primarySource)}</span>
                          {job.isNew && <span className="new-chip">New</span>}
                        </div>
                        <p className="muted">
                          {job.company} · {job.location}
                          {job.employmentType ? ` · ${job.employmentType}` : ''}
                        </p>
                        {also && (
                          <p
                            className="also-chip"
                            title={job.sources.map((item) => `${sourceTitle(item.source)} · ${item.domain}`).join('\n')}
                          >
                            {also}
                            {job.sources.filter((item) => item.source !== job.primarySource).length
                              ? ` (${job.sources.filter((item) => item.source !== job.primarySource).length})`
                              : ''}
                          </p>
                        )}
                      </button>
                      <div className="job-card-match">
                        <MatchBadge
                          match={match}
                          threshold={threshold}
                          onWhy={() => match && setWhyMatch(match)}
                          onRetry={() => void scoreJobs([job])}
                        />
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
          {filters.pagination === 'infinite' && <div ref={sentinel} className="feed-sentinel" />}
          {loadingMore && <p className="muted">Loading more jobs…</p>}
          {filters.pagination === 'pages' && total > 0 && (
            <nav className="pager" aria-label="Job pages">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => {
                  const next = page - 1
                  setPage(next)
                  void loadPage(String((next - 1) * PAGE_SIZE), false)
                }}
              >
                Previous
              </button>
              <span className="muted">
                Page {page} of {pageCount}
              </span>
              <button
                type="button"
                disabled={page >= pageCount}
                onClick={() => {
                  const next = page + 1
                  setPage(next)
                  void loadPage(String((next - 1) * PAGE_SIZE), false)
                }}
              >
                Next
              </button>
            </nav>
          )}
        </div>

        {selected && (
          <aside className="job-drawer" role="dialog" aria-modal="true" aria-labelledby="job-drawer-title">
            <div className="job-drawer-head">
              <h2 id="job-drawer-title">{selected.title}</h2>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setSelected(null)
                  if (window.location.hash !== '#/jobs') window.location.hash = '#/jobs'
                }}
                aria-label="Close details"
              >
                Close
              </button>
            </div>
            <div className="drawer-tabs" role="tablist" aria-label="Job details">
              <button
                type="button"
                role="tab"
                aria-selected={drawerTab === 'details'}
                className={drawerTab === 'details' ? 'is-selected' : ''}
                onClick={() => selectJob(selected, 'details')}
              >
                Details
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={drawerTab === 'emails'}
                className={drawerTab === 'emails' ? 'is-selected' : ''}
                onClick={() => selectJob(selected, 'emails')}
              >
                Emails
              </button>
            </div>
            <JobCrossLinks jobId={selected.id} resumeId={resumeId} current="jobs" />
            {drawerTab === 'emails' && <JobEmailsTab jobId={selected.id} />}
            {drawerTab === 'details' && detailLoading && <p className="skeleton">Loading details…</p>}
            {drawerTab === 'details' && !detailLoading && detail && (
              <>
                <p className="muted">
                  {detail.company} · {detail.location}
                </p>
                <MatchMeter match={matches[selected.id]} threshold={threshold} />
                {matches[selected.id]?.state === 'error' && (
                  <button type="button" className="link-btn" onClick={() => void scoreJobs([selected])}>
                    Retry match
                  </button>
                )}
                {matches[selected.id]?.state === 'computed' && matches[selected.id].score != null && (
                  <label className="chip-toggle">
                    <input
                      type="checkbox"
                      checked={
                        saveOverride[selected.id] ??
                        Boolean(matches[selected.id].persisted || (matches[selected.id].score ?? 0) >= threshold)
                      }
                      onChange={(event) => {
                        const checked = event.target.checked
                        setSaveOverride((prev) => ({ ...prev, [selected.id]: checked }))
                        if (checked) void saveMatch(selected)
                      }}
                    />
                    Save match
                  </label>
                )}
                <WhyThisScoreInline match={matches[selected.id]} />
                {detail.descriptionError && <p className="warn-text">{detail.descriptionError}</p>}
                <p>{detail.description}</p>
                <h3>Sources</h3>
                <ul className="source-links">
                  {detail.sources.map((item) => (
                    <li key={`${item.source}-${item.sourceUrl}`}>
                      <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                        {sourceTitle(item.source)} · {item.domain}
                      </a>
                    </li>
                  ))}
                </ul>
                <p>
                  <a className="primary-link" href={detail.applyUrl} target="_blank" rel="noreferrer">
                    Apply on posting
                  </a>
                </p>
              </>
            )}
          </aside>
        )}
      </div>

      <div className="feed-sticky-refresh">
        <button type="button" className="primary" disabled={offline} onClick={() => void refresh('all')}>
          Refresh
        </button>
      </div>
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
      {whyMatch && <WhyThisScore match={whyMatch} onClose={() => setWhyMatch(null)} />}
    </div>
  )
}
