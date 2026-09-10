export type JobSource = 'greenhouse' | 'lever' | 'manual'
export type CoverLetterMode = 'none' | 'upload' | 'generate'
export type ApplyState =
  | 'created'
  | 'queued'
  | 'submitting'
  | 'submitted'
  | 'packaged'
  | 'failed'
  | 'cancelled'
  | 'rate_limited'

export type ApplySummary = {
  request_id: string
  state: ApplyState | string
  vendor: JobSource | string
  mode: string
  job_id: string | null
  posting_url: string | null
  created_at: string
  updated_at: string
  failure_reason: string | null
}

export type ApplyDetail = {
  request_id: string
  state: ApplyState | string
  state_history: { event: string; at: string; payload?: Record<string, unknown> }[]
  source: {
    type: string
    job_posting_id: string | null
    posting_url: string | null
    external_application_id?: string | null
  }
  artifacts: {
    resume_blob_sas: string | null
    cover_letter_blob_sas: string | null
    package_blob_sas: string | null
    deep_link_url: string | null
  }
  autofill: { field_key: string; value: string; required: boolean; source: string }[]
  cover_letter_text?: string | null
  cover_letter_source?: string | null
  validation_errors: unknown
  failure_reason: string | null
  submitted_at: string | null
  packaged_at: string | null
  created_at: string
  updated_at: string
  captcha?: boolean
  manual_fallback?: boolean
  retry_count?: number
  manual_next_steps?: string | null
}

export type CreateApplyBody = {
  job_source: JobSource
  job_posting_id?: string
  posting_url?: string
  resume_id?: string
  cover_letter_mode: CoverLetterMode
  consent_approved: boolean
  answers?: Record<string, string>
}

export type AutoApplyApi = {
  create(body: CreateApplyBody): Promise<{ request_id: string; state: string; created_at: string }>
  list(state?: string): Promise<{ items: ApplySummary[] }>
  get(requestId: string): Promise<ApplyDetail>
  cancel(requestId: string): Promise<{ state: string; request_id: string }>
}
