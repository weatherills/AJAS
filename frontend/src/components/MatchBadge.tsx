import type { MatchView } from '../api/matchingTypes'
import {
  CHIP_VISIBLE,
  chipOverflow,
  displayScore,
  isOutdated,
  scoreBand,
  scoreLabel,
  TERM_TOOLTIP,
} from '../lib/matching'

export function MatchBadge({
  match,
  threshold,
  onWhy,
  onRetry,
}: {
  match: MatchView | undefined
  threshold: number
  onWhy?: () => void
  onRetry?: () => void
}) {
  if (!match || match.state === 'loading') {
    return (
      <span className="match-badge match-skeleton" aria-hidden="true">
        Loading match
      </span>
    )
  }
  if (match.state === 'no_resume') {
    return (
      <a className="match-cta" href="#/resumes" onClick={(event) => event.stopPropagation()}>
        Add resume to see match
      </a>
    )
  }
  if (match.state === 'insufficient') {
    return (
      <span className="match-muted" title="The posting does not include enough text to score.">
        Not enough data to score.
      </span>
    )
  }
  if (match.state === 'error' || match.score == null) {
    return (
      <span className="match-error">
        <span title={match.error || 'Could not compute match'}>—</span>
        {onRetry && (
          <button
            type="button"
            className="link-btn"
            onClick={(event) => {
              event.stopPropagation()
              onRetry()
            }}
          >
            Retry
          </button>
        )}
      </span>
    )
  }

  const band = scoreBand(match.score)
  const label = scoreLabel(match.score)
  const shown = displayScore(match.score)
  const meets = match.score >= threshold
  const tooltipTerms = match.terms.slice(0, TERM_TOOLTIP)
  const chips = chipOverflow(match.terms, CHIP_VISIBLE)
  const tipId = `match-tip-${match.jobId}`

  return (
    <div className="match-badge-wrap">
      <button
        type="button"
        className={`match-badge match-${band}`}
        aria-describedby={tipId}
        title={`${match.score.toFixed(1)}% · ${label}`}
        onClick={(event) => {
          event.stopPropagation()
          onWhy?.()
        }}
      >
        <span className="match-pct">{shown}%</span>
        <span className="match-label">{label}</span>
      </button>
      {meets && <span className="match-meets">Meets threshold</span>}
      {isOutdated(match.versions) && (
        <span className="match-outdated" title="Recomputed with a newer model may differ.">
          Outdated
        </span>
      )}
      <div id={tipId} className="match-tooltip" role="tooltip">
        <p>
          {match.score.toFixed(1)}% · Keywords {Math.round((match.breakdown?.weights.keyword || 0.4) * 100)}% • Semantic{' '}
          {Math.round((match.breakdown?.weights.semantic || 0.6) * 100)}%
        </p>
        {tooltipTerms.length > 0 && <p>Top terms: {tooltipTerms.join(', ')}</p>}
        <div className="match-chips">
          {chips.shown.map((term) => (
            <span key={term} className="match-chip">
              {term}
            </span>
          ))}
          {chips.extra > 0 && <span className="match-chip">+{chips.extra} more</span>}
        </div>
        {onWhy && (
          <span className="muted">
            Why this score
          </span>
        )}
      </div>
    </div>
  )
}
