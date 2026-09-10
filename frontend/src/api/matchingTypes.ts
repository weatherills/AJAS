export type MatchBreakdown = {
  keyword: number
  semantic: number
  weights: { keyword: number; semantic: number }
}

export type MatchView = {
  jobId: string
  resumeId: string | null
  score: number | null
  state: import('../lib/matching').MatchState
  breakdown: MatchBreakdown | null
  terms: string[]
  explanation: string
  versions: import('../lib/matching').MatchVersions | null
  computedAt: string | null
  persisted: boolean
  matchId?: string
  error?: string | null
}

export type MatchScoreQuery = {
  resumeId: string | null
  resumeText: string
  jobs: { id: string; text: string }[]
  threshold: number
  explanation?: boolean
  persist?: boolean
}

export type MatchingApi = {
  scoreMany(query: MatchScoreQuery): Promise<MatchView[]>
  scoreOne(query: Omit<MatchScoreQuery, 'jobs'> & { job: { id: string; text: string } }): Promise<MatchView>
}
