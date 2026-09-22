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
  evidence?: string[]
  highlights?: string[]
  gaps?: string[]
  bucket?: { key: string; label: string; min: number; score: number }
  gate?: {
    required: string[]
    niceToHave: string[]
    matchedRequired: string[]
    missingRequired: string[]
    coverage: number
  }
}

export type MatchScoreQuery = {
  resumeId: string | null
  resumeText: string
  jobs: { id: string; text: string }[]
  threshold: number
  explanation?: boolean
  persist?: boolean
}

export type MatchRecord = {
  id: string
  userId?: string
  jobId: string
  resumeId: string
  modelVersion?: string
  score: number
  createdAt?: string
  updatedAt?: string
  latest?: boolean
  _etag?: string
}

export type MatchRecordDetail = {
  record: MatchRecord
  evidence: { id: string; sentences: string[]; createdAt?: string }[]
}

export type MatchingApi = {
  scoreMany(query: MatchScoreQuery): Promise<MatchView[]>
  scoreOne(query: Omit<MatchScoreQuery, 'jobs'> & { job: { id: string; text: string } }): Promise<MatchView>
  listResults(query: { resumeId: string; jobIds?: string[] }): Promise<MatchView[]>
  listRecords(query?: { jobId?: string; resumeId?: string }): Promise<MatchRecord[]>
  getRecord(matchId: string): Promise<MatchRecordDetail>
  rescore(matchId: string, score?: number): Promise<{ record: MatchRecord }>
  batchRescore(pairs: { jobId: string; resumeId: string; score: number }[]): Promise<{ count: number; items: MatchRecord[] }>
  warmup(): Promise<{ warm: boolean; elapsedMs: number }>
}
