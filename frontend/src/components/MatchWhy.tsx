import { useState } from 'react'
import type { MatchView } from '../api/matchingTypes'
import { copyText, explanationClipboardPayload } from '../lib/clipboard'
import { EXPLAIN_MAX, EXPLAIN_PREVIEW, truncateExplanation } from '../lib/matching'
import { fitSubScoreTooltips, groupEvidence, truncateChip } from '../lib/sprint15Kanban'
import { Modal } from './Modal'

export function WhyThisScore({ match, onClose }: { match: MatchView; onClose: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const source = (match.explanation || 'No explanation is available for this score.').slice(0, EXPLAIN_MAX)
  const preview = truncateExplanation(source, EXPLAIN_PREVIEW)
  const text = expanded ? source : preview.text
  return (
    <Modal title="Why this score" onClose={onClose}>
      <p className="why-body">{text}</p>
      {preview.truncated && (
        <button type="button" className="link-btn" onClick={() => setExpanded((value) => !value)}>
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
      {match.breakdown && (
        <p className="muted">
          Keywords {match.breakdown.keyword.toFixed(1)} · Semantic {match.breakdown.semantic.toFixed(1)} · Weights{' '}
          {Math.round(match.breakdown.weights.keyword * 100)}% / {Math.round(match.breakdown.weights.semantic * 100)}%
          {' · '}
          {fitSubScoreTooltips(match.breakdown.keyword, match.breakdown.semantic, 0).tips.keyword}
        </p>
      )}
      {match.bucket && <p className="muted">Fit bucket: {match.bucket.label}</p>}
      {match.highlights && match.highlights.length > 0 && (
        <ul className="match-chips" aria-label="Match reasons">
          {groupEvidence(match.highlights.slice(0, 8), match.gaps || []).skills.map((chip) => {
            const shown = truncateChip(chip.label)
            return (
              <li key={chip.label} title={chip.detail}>
                {shown.label}
              </li>
            )
          })}
        </ul>
      )}
      {match.gaps && match.gaps.length > 0 && (
        <p className="muted" role="status">
          Missing must-haves: {match.gaps.slice(0, 6).join(', ')}
        </p>
      )}
      {match.evidence && match.evidence.length > 0 && (
        <ul className="evidence-list">
          {match.evidence.slice(0, 5).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <div className="modal-actions">
        <button
          type="button"
          className="secondary"
          aria-label="Copy explanation"
          onClick={() => {
            void copyText(explanationClipboardPayload(match))
          }}
        >
          Copy
        </button>
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  )
}

export function WhyThisScoreInline({ match }: { match: MatchView | undefined }) {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  if (!match || match.state !== 'computed') return null
  const source = (match.explanation || '').slice(0, EXPLAIN_MAX)
  const preview = truncateExplanation(source, EXPLAIN_PREVIEW)
  const text = expanded ? source : preview.text
  return (
    <section className="why-inline">
      <button type="button" className="link-btn" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        Why this score
      </button>
      {open && (
        <div>
          <p className="why-body">{text || 'No explanation is available for this score.'}</p>
          {preview.truncated && (
            <button type="button" className="link-btn" onClick={() => setExpanded((value) => !value)}>
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
          {match.highlights && match.highlights.length > 0 && (
            <ul className="match-chips" aria-label="Match reasons">
              {groupEvidence(match.highlights.slice(0, 8), match.gaps || []).skills.map((chip) => (
                <li key={chip.label} title={chip.detail}>
                  {truncateChip(chip.label).label}
                </li>
              ))}
            </ul>
          )}
          {match.gaps && match.gaps.length > 0 && (
            <p className="muted" role="status">
              Missing must-haves: {match.gaps.slice(0, 6).join(', ')}
            </p>
          )}
          {match.evidence && match.evidence.length > 0 && (
            <ul className="evidence-list">
              {match.evidence.slice(0, 5).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
