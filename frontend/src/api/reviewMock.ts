import type { ReviewDecision, ReviewMatch, ReviewApi } from './reviewTypes'
import { applyFilters, COMMENT_MAX } from '../lib/review'
import { recordMockDecision } from './learningMock'

type Row = ReviewMatch & { decisions: ReviewDecision[] }

const rows = new Map<string, Row>()
let failNext = false

function stamp(offsetHours = 0) {
  return new Date(Date.now() - offsetHours * 3600_000).toISOString()
}

function seedRow(partial: Partial<Row> & Pick<Row, 'matchId' | 'jobTitle' | 'company'>): Row {
  const createdAt = partial.createdAt || stamp(2)
  const status = partial.status || 'pending'
  const row: Row = {
    matchId: partial.matchId,
    jobId: partial.jobId || partial.matchId.replace('match-', 'job-'),
    resumeId: partial.resumeId === undefined ? 'seed-ready' : partial.resumeId,
    jobTitle: partial.jobTitle,
    company: partial.company,
    location: partial.location || 'Remote',
    score: partial.score === undefined ? 80 : partial.score,
    suggestion: partial.suggestion || 'approve',
    status,
    source: partial.source || 'ai',
    createdAt,
    updatedAt: partial.updatedAt || createdAt,
    queuedAt: partial.queuedAt || createdAt,
    etag: partial.etag || '1',
    postingUrl: partial.postingUrl || `https://jobs.example.com/${partial.matchId}`,
    applied: partial.applied ?? status === 'approved',
    summary: partial.summary === undefined ? 'Strong overlap on platform work, Python, and Azure.' : partial.summary,
    why: partial.why === undefined ? 'The resume matches core backend and platform keywords in this posting.' : partial.why,
    highlights: partial.highlights === undefined ? ['Python services', 'Azure', 'Kubernetes', 'Staff-level scope'] : partial.highlights,
    resumeHighlights:
      partial.resumeHighlights === undefined
        ? {
            matched: ['Python', 'Azure', 'APIs'],
            missing: ['Go'],
            years: '8+ years vs 5 required',
            keywords: ['platform', 'distributed systems'],
          }
        : partial.resumeHighlights,
    decidedAt: partial.decidedAt || null,
    latestDecisionId: partial.latestDecisionId || null,
    comment: partial.comment || null,
    decision: partial.decision || null,
    scoreAtDecision: partial.scoreAtDecision ?? null,
    archived: partial.archived ?? false,
    priority: partial.priority ?? 0,
    assigneeId: partial.assigneeId ?? null,
    decisions: partial.decisions || [],
  }
  rows.set(row.matchId, row)
  return row
}

function seed() {
  if (rows.size) return
  seedRow({
    matchId: 'match-staff',
    jobId: 'job-1',
    jobTitle: 'Staff Platform Engineer',
    company: 'Acme',
    location: 'Remote',
    score: 88,
    suggestion: 'approve',
    why: 'Resume shows staff-level platform delivery, Python services, and Azure experience that map to this posting.',
    queuedAt: stamp(6),
  })
  seedRow({
    matchId: 'match-data',
    jobId: 'job-13',
    jobTitle: 'Data Engineer',
    company: 'Globex',
    location: 'Austin, TX',
    score: 72,
    suggestion: 'review',
    summary: 'Solid data fundamentals with some gaps in warehouse tooling.',
    highlights: ['Python', 'SQL', 'Pipelines'],
    queuedAt: stamp(5),
  })
  seedRow({
    matchId: 'match-design',
    jobTitle: 'Product Designer',
    company: 'Initech',
    location: 'New York, NY',
    score: 41,
    suggestion: 'reject',
    summary: 'Design-heavy role; resume is engineering-first.',
    queuedAt: stamp(4),
  })
  seedRow({
    matchId: 'match-sparse',
    jobTitle: 'Security Engineer',
    company: 'Umbrella',
    location: 'Remote',
    score: 80,
    suggestion: 'none',
    summary: null,
    why: null,
    highlights: null,
    queuedAt: stamp(3),
  })
  seedRow({
    matchId: 'match-saved',
    jobTitle: 'Product Manager',
    company: 'Soylent',
    location: 'San Francisco, CA',
    source: 'saved',
    score: null,
    suggestion: 'none',
    summary: 'You saved this posting to decide later.',
    why: null,
    highlights: ['Roadmaps', 'B2B SaaS'],
    queuedAt: stamp(8),
  })
  seedRow({
    matchId: 'match-no-resume',
    jobTitle: 'Backend Engineer',
    company: 'Hooli',
    location: 'Remote',
    resumeId: null,
    resumeHighlights: null,
    score: 77,
    suggestion: 'review',
    queuedAt: stamp(2),
  })
  const approvedAt = stamp(30)
  seedRow({
    matchId: 'match-approved',
    jobTitle: 'Platform Engineer',
    company: 'Acme',
    location: 'Remote',
    score: 91,
    suggestion: 'approve',
    status: 'approved',
    applied: true,
    decidedAt: approvedAt,
    latestDecisionId: 'dec-approved',
    comment: 'Great platform fit — apply this week.',
    decision: 'approve',
    scoreAtDecision: 91,
    queuedAt: stamp(40),
    decisions: [
      {
        decisionId: 'dec-approved',
        matchId: 'match-approved',
        decision: 'approve',
        comment: 'Great platform fit — apply this week.',
        source: 'manual',
        version: 1,
        createdAt: approvedAt,
        actor: 'local-user',
        supersedesDecisionId: null,
        aiScore: 91,
        suggestion: 'approve',
      },
    ],
  })
  const rejectedAt = stamp(20)
  seedRow({
    matchId: 'match-rejected',
    jobTitle: 'Technical Recruiter',
    company: 'Massive Dynamic',
    location: 'Boston, MA',
    source: 'saved',
    score: 55,
    suggestion: 'reject',
    status: 'rejected',
    decidedAt: rejectedAt,
    latestDecisionId: 'dec-rejected',
    comment: 'Not looking for recruiting roles.',
    decision: 'reject',
    scoreAtDecision: 55,
    queuedAt: stamp(28),
    decisions: [
      {
        decisionId: 'dec-rejected',
        matchId: 'match-rejected',
        decision: 'reject',
        comment: 'Not looking for recruiting roles.',
        source: 'manual',
        version: 1,
        createdAt: rejectedAt,
        actor: 'local-user',
        supersedesDecisionId: null,
        aiScore: 55,
        suggestion: 'reject',
      },
    ],
  })
}

function cloneMatch(row: Row): ReviewMatch {
  const { decisions: _decisions, ...match } = row
  return structuredClone(match)
}

export function resetReviewMock() {
  rows.clear()
  failNext = false
  seed()
}

export function setReviewFailNext(value = true) {
  failNext = value
}

resetReviewMock()

export const mockReviewApi: ReviewApi = {
  async list(tab, filters) {
    seed()
    const items = applyFilters([...rows.values()].map(cloneMatch), tab, filters)
    return { items, total: items.length }
  },
  async get(matchId, opts) {
    seed()
    const row = rows.get(matchId)
    if (!row) throw new Error('Not found')
    const snapshot = opts?.decisionId ? row.decisions.find((item) => item.decisionId === opts.decisionId) : null
    const decision = snapshot || row.decisions.find((item) => item.decisionId === row.latestDecisionId) || null
    const snapshotUnavailable = Boolean(opts?.decisionId && !snapshot)
    return {
      match: cloneMatch(row),
      decision: decision ? structuredClone(decision) : null,
      blobs: {
        jobUrl: row.postingUrl,
        resumeUrl: row.resumeId ? `https://blob.local/resumes/${row.resumeId}` : null,
      },
      snapshotUnavailable,
    }
  },
  async decide(matchId, body, meta) {
    seed()
    const row = rows.get(matchId)
    if (!row) throw new Error('Not found')
    if (failNext) {
      failNext = false
      throw new Error('Could not save decision. Try again.')
    }
    const comment = (body.comment || '').trim()
    if (comment.length > COMMENT_MAX) throw new Error(`Comments can be at most ${COMMENT_MAX} characters.`)
    if (meta.etag && row.etag !== meta.etag) throw new Error('This match changed. Refresh and try again.')
    if (row.status !== 'pending' && !body.overwrite) throw new Error('Already decided')
    const existing = row.decisions.find((item) => item.decisionId === `idem-${meta.idempotencyKey}`)
    if (existing) {
      return { decisionId: existing.decisionId, matchStatus: row.status, version: existing.version, occurredAt: existing.createdAt }
    }
    const now = stamp(0)
    const event: ReviewDecision = {
      decisionId: `idem-${meta.idempotencyKey}`,
      matchId,
      decision: body.decision,
      comment: comment || null,
      source: 'manual',
      version: row.decisions.length + 1,
      createdAt: now,
      actor: 'local-user',
      supersedesDecisionId: row.latestDecisionId,
      aiScore: row.score,
      suggestion: row.suggestion,
    }
    row.decisions.push(event)
    row.status = body.decision === 'approve' ? 'approved' : 'rejected'
    row.applied = row.status === 'approved'
    row.latestDecisionId = event.decisionId
    row.decidedAt = now
    row.comment = event.comment
    row.decision = event.decision
    row.scoreAtDecision = row.score
    row.updatedAt = now
    row.etag = String(Number(row.etag || '1') + 1)
    recordMockDecision(matchId, body.decision)
    return { decisionId: event.decisionId, matchStatus: row.status, version: event.version, occurredAt: now }
  },
  async reopen(matchId) {
    seed()
    const row = rows.get(matchId)
    if (!row) throw new Error('Not found')
    if (row.decision === 'approve' || row.decision === 'reject') {
      recordMockDecision(matchId, 'undo')
    }
    row.status = 'pending'
    row.applied = false
    row.decidedAt = null
    row.latestDecisionId = null
    row.decision = null
    row.comment = null
    row.updatedAt = stamp(0)
    row.etag = String(Number(row.etag || '1') + 1)
    return cloneMatch(row)
  },
  async bulk(body) {
    seed()
    for (const id of body.matchIds) {
      const row = rows.get(id)
      if (!row) continue
      if (body.action === 'archive') row.archived = true
      if (body.action === 'unarchive') row.archived = false
      if (body.action === 'prioritize') row.priority = 1
      if (body.action === 'assign') row.assigneeId = body.assigneeId || 'local-user'
    }
    return { action: body.action, updated: body.matchIds, count: body.matchIds.length }
  },
}

export function _reviewRowsForTests() {
  seed()
  return rows
}
