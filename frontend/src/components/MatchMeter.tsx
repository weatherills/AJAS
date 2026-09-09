import type { MatchView } from '../api/matchingTypes'
import { displayScore, formatUtc, isOutdated, scoreBand, scoreLabel } from '../lib/matching'

export function MatchMeter({
  match,
  threshold,
}: {
  match: MatchView | undefined
  threshold: number
}) {
  if (!match || match.state === 'loading') {
    return <div className="match-meter match-skeleton" aria-hidden="true" />
  }
  if (match.state === 'no_resume') {
    return (
      <p>
        <a href="#/resumes">Add resume to see match</a>
      </p>
    )
  }
  if (match.state === 'insufficient') {
    return <p className="muted">Not enough data to score.</p>
  }
  if (match.state === 'error' || match.score == null) {
    return (
      <p className="match-error" title={match.error || 'Could not compute match'}>
        —
      </p>
    )
  }
  const band = scoreBand(match.score)
  const shown = displayScore(match.score)
  const meets = match.score >= threshold
  return (
    <div className="match-meter-block">
      <div
        className={`match-meter match-${band}`}
        style={{ ['--pct' as string]: String(shown) }}
        role="img"
        aria-label={`Match score ${shown} percent, ${scoreLabel(match.score)}`}
      >
        <span>{shown}%</span>
      </div>
      <div>
        <p className={`match-label match-${band}`}>{scoreLabel(match.score)}</p>
        {meets && <span className="match-meets">Meets threshold</span>}
        {isOutdated(match.versions) && (
          <span className="match-outdated" title="Recomputed with a newer model may differ.">
            Outdated
          </span>
        )}
        {match.versions && (
          <button
            type="button"
            className="match-info"
            title={`Model ${match.versions.embeddingsModel} · ${match.versions.algorithm} · range 0–100% · last computed ${formatUtc(match.computedAt)}`}
            aria-label="View model and version"
          >
            i
          </button>
        )}
      </div>
    </div>
  )
}
