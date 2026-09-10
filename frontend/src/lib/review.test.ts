import { describe, expect, it } from 'vitest'
import { mockReviewApi, resetReviewMock, setReviewFailNext } from '../api/reviewMock'
import {
  applyFilters,
  COMMENT_MAX,
  DEFAULT_FILTERS,
  findReviewRow,
  nextAfterRemove,
  suggestionLabel,
  tabForMatch,
  truncateText,
  validateComment,
} from './review'

describe('review helpers', () => {
  it('enforces the 1000 character comment limit', () => {
    expect(validateComment('  keep this ').value.startsWith('keep')).toBe(true)
    const over = validateComment('x'.repeat(COMMENT_MAX + 8))
    expect(over.error).toBeTruthy()
    expect(over.value).toHaveLength(COMMENT_MAX)
    expect(over.remaining).toBe(0)
  })

  it('labels suggestions and truncates comments', () => {
    expect(suggestionLabel('approve')).toBe('Recommend Approve')
    expect(suggestionLabel('none')).toBe('No suggestion available')
    const cut = truncateText('Great platform fit — apply this week.', 12)
    expect(cut.truncated).toBe(true)
    expect(cut.text.length).toBeLessThanOrEqual(12)
  })

  it('selects the next queue row after a decision', () => {
    expect(nextAfterRemove(['a', 'b', 'c'], 'b')).toBe('c')
    expect(nextAfterRemove(['a'], 'a')).toBe(null)
  })
})

describe('mock review api', () => {
  it('lists AI matches awaiting a decision, sorted by score', async () => {
    resetReviewMock()
    const result = await mockReviewApi.list('matches', { ...DEFAULT_FILTERS, source: 'ai', status: 'awaiting' })
    expect(result.items.every((item) => item.source === 'ai' && item.status === 'pending')).toBe(true)
    expect(result.items[0].jobTitle).toBe('Staff Platform Engineer')
    expect(result.items[0].jobId).toBe('job-1')
    expect(result.items[0].score).toBe(88)
  })

  it('filters saved jobs separately from matches', async () => {
    resetReviewMock()
    const saved = await mockReviewApi.list('saved', { ...DEFAULT_FILTERS, source: 'saved', status: 'awaiting' })
    expect(saved.items.map((item) => item.jobTitle)).toEqual(['Product Manager'])
  })

  it('persists a decision, leaves the queue, and keeps history on reopen', async () => {
    resetReviewMock()
    const before = await mockReviewApi.list('matches', { ...DEFAULT_FILTERS, source: 'ai' })
    const staff = before.items.find((item) => item.matchId === 'match-staff')
    expect(staff).toBeTruthy()
    const saved = await mockReviewApi.decide(
      'match-staff',
      { decision: 'approve', comment: 'Ship it' },
      { etag: staff!.etag, idempotencyKey: 'k1' },
    )
    expect(saved.matchStatus).toBe('approved')
    const queue = await mockReviewApi.list('matches', { ...DEFAULT_FILTERS, source: 'ai' })
    expect(queue.items.some((item) => item.matchId === 'match-staff')).toBe(false)
    const history = await mockReviewApi.list('history', { ...DEFAULT_FILTERS, status: 'all', source: 'all' })
    const row = history.items.find((item) => item.matchId === 'match-staff')
    expect(row?.comment).toBe('Ship it')
    expect(row?.decision).toBe('approve')
    await mockReviewApi.reopen('match-staff')
    const reopened = await mockReviewApi.list('matches', { ...DEFAULT_FILTERS, source: 'ai' })
    expect(reopened.items.some((item) => item.matchId === 'match-staff' && item.status === 'pending')).toBe(true)
    const still = await mockReviewApi.get('match-staff', { decisionId: saved.decisionId })
    expect(still.decision?.comment).toBe('Ship it')
    expect(still.match.status).toBe('pending')
  })

  it('keeps the comment when save fails', async () => {
    resetReviewMock()
    setReviewFailNext(true)
    await expect(
      mockReviewApi.decide('match-staff', { decision: 'approve', comment: 'keep me' }, { etag: '1', idempotencyKey: 'x' }),
    ).rejects.toThrow('Could not save decision')
    const detail = await mockReviewApi.get('match-staff')
    expect(detail.match.status).toBe('pending')
  })

  it('filters history with applyFilters', async () => {
    resetReviewMock()
    const history = await mockReviewApi.list('history', { ...DEFAULT_FILTERS, status: 'all', source: 'all', minScore: 80 })
    expect(history.items.every((item) => (item.scoreAtDecision ?? 0) >= 80)).toBe(true)
    const acme = applyFilters(history.items, 'history', { ...DEFAULT_FILTERS, status: 'all', source: 'all', company: 'Acme' })
    expect(acme.every((item) => item.company === 'Acme')).toBe(true)
  })
})

describe('review deep-links', () => {
  it('maps decided matches to history and saved pending to saved', () => {
    expect(tabForMatch({ status: 'approved', source: 'ai' })).toBe('history')
    expect(tabForMatch({ status: 'pending', source: 'saved' })).toBe('saved')
    expect(tabForMatch({ status: 'pending', source: 'ai' })).toBe('matches')
  })

  it('finds a match by id and a job that only exists in history', async () => {
    resetReviewMock()
    const byId = await findReviewRow(mockReviewApi, { matchId: 'match-approved' })
    expect(byId?.tab).toBe('history')
    expect(byId?.match.jobTitle).toBe('Platform Engineer')
    const byJob = await findReviewRow(mockReviewApi, { jobId: 'job-1' })
    expect(byJob?.match.matchId).toBe('match-staff')
    const byResume = await findReviewRow(mockReviewApi, { resumeId: 'seed-ready' })
    expect(byResume?.match.resumeId).toBe('seed-ready')
  })
})
