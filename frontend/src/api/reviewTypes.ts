export type ReviewTab = 'matches' | 'saved' | 'history'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type ReviewSource = 'ai' | 'saved'
export type Suggestion = 'approve' | 'reject' | 'none' | 'review'
export type DecisionValue = 'approve' | 'reject'

export type ResumeHighlights = {
  matched: string[]
  missing: string[]
  years: string | null
  keywords: string[]
}

export type ReviewMatch = {
  matchId: string
  jobId: string
  resumeId: string | null
  jobTitle: string
  company: string
  location: string
  score: number | null
  suggestion: Suggestion
  status: ReviewStatus
  source: ReviewSource
  createdAt: string
  updatedAt: string
  queuedAt: string
  etag: string
  postingUrl: string | null
  applied: boolean
  summary: string | null
  why: string | null
  highlights: string[] | null
  resumeHighlights: ResumeHighlights | null
  decidedAt: string | null
  latestDecisionId: string | null
  comment: string | null
  decision: DecisionValue | null
  scoreAtDecision: number | null
}

export type ReviewDecision = {
  decisionId: string
  matchId: string
  decision: DecisionValue
  comment: string | null
  source: 'manual' | 'system'
  version: number
  createdAt: string
  actor: string
  supersedesDecisionId: string | null
  aiScore: number | null
  suggestion: Suggestion | null
}

export type ReviewDetail = {
  match: ReviewMatch
  decision: ReviewDecision | null
  blobs: { jobUrl: string | null; resumeUrl: string | null }
  snapshotUnavailable: boolean
}

export type ReviewFilters = {
  minScore: number
  maxScore: number
  company: string
  location: string
  source: 'all' | ReviewSource
  status: 'all' | 'awaiting' | 'approved' | 'rejected'
  createdAfter: string
  sort: 'score' | 'date' | 'company' | 'title'
}

export type ReviewApi = {
  list(tab: ReviewTab, filters: ReviewFilters): Promise<{ items: ReviewMatch[]; total: number }>
  get(matchId: string, opts?: { decisionId?: string }): Promise<ReviewDetail>
  decide(
    matchId: string,
    body: { decision: DecisionValue; comment?: string; overwrite?: boolean },
    meta: { etag: string; idempotencyKey: string },
  ): Promise<{ decisionId: string; matchStatus: ReviewStatus; version: number; occurredAt: string }>
  reopen(matchId: string): Promise<ReviewMatch>
}
