import type { ApplyDetail, ApplySummary, AutoApplyApi, CreateApplyBody } from './autoApplyTypes'

const rows = new Map<string, ApplyDetail>()

function now() {
  return new Date().toISOString()
}

function needsManual(source: string, url?: string) {
  if (source === 'manual') return true
  const hay = (url || '').toLowerCase()
  return ['captcha', 'sso', 'unsupported', 'manual'].some((token) => hay.includes(token))
}

export function resetAutoApplyMock() {
  rows.clear()
}

export const mockAutoApplyApi: AutoApplyApi = {
  async create(body: CreateApplyBody) {
    if (!body.consent_approved) throw new Error('consent_approved must be true')
    if (!body.job_posting_id && !body.posting_url) throw new Error('job_posting_id or posting_url is required')
    const existing = [...rows.values()].find(
      (row) =>
        row.source.job_posting_id === (body.job_posting_id || null) &&
        !['submitted', 'failed', 'cancelled', 'packaged'].includes(row.state),
    )
    if (existing) throw new Error(`Duplicate in-flight request (${existing.request_id})`)
    const requestId = `req-${rows.size + 1}`
    const stamped = now()
    const packaged = needsManual(body.job_source, body.posting_url)
    const detail: ApplyDetail = {
      request_id: requestId,
      state: packaged ? 'packaged' : 'submitted',
      state_history: packaged
        ? [
            { event: 'queued', at: stamped },
            { event: 'needs_review', at: stamped },
          ]
        : [
            { event: 'queued', at: stamped },
            { event: 'submission_succeeded', at: stamped },
          ],
      source: {
        type: body.job_source,
        job_posting_id: body.job_posting_id || null,
        posting_url: body.posting_url || null,
        external_application_id: packaged ? null : `${body.job_source}-${requestId.slice(-8)}`,
      },
      artifacts: {
        resume_blob_sas: 'https://blob.local/resume.pdf',
        cover_letter_blob_sas: body.cover_letter_mode === 'none' ? null : 'https://blob.local/cover.pdf',
        package_blob_sas: packaged ? 'https://blob.local/package.zip' : null,
        deep_link_url: body.posting_url || null,
      },
      autofill: [
        { field_key: 'full_name', value: 'Alex Jobseeker', required: true, source: 'profile' },
        { field_key: 'email', value: 'alex@example.com', required: true, source: 'profile' },
      ],
      cover_letter_text:
        body.cover_letter_mode === 'generate'
          ? 'Dear hiring team,\n\nI am writing to apply. Sincerely,\nAlex Jobseeker\n'
          : null,
      cover_letter_source: body.cover_letter_mode === 'generate' ? 'ai' : null,
      validation_errors: null,
      failure_reason: null,
      submitted_at: packaged ? null : stamped,
      packaged_at: packaged ? stamped : null,
      created_at: stamped,
      updated_at: stamped,
    }
    rows.set(requestId, detail)
    return { request_id: requestId, state: detail.state, created_at: stamped }
  },
  async list() {
    const items: ApplySummary[] = [...rows.values()].map((row) => ({
      request_id: row.request_id,
      state: row.state,
      vendor: row.source.type,
      mode: row.state === 'packaged' ? 'manual_package' : 'api',
      job_id: row.source.job_posting_id,
      posting_url: row.source.posting_url,
      created_at: row.created_at,
      updated_at: row.updated_at,
      failure_reason: row.failure_reason,
    }))
    return { items }
  },
  async get(requestId) {
    const row = rows.get(requestId)
    if (!row) throw new Error('not found')
    return row
  },
  async cancel(requestId) {
    const row = rows.get(requestId)
    if (!row) throw new Error('not found')
    if (row.state !== 'queued' && row.state !== 'created') throw new Error('cannot cancel after submission has started')
    row.state = 'cancelled'
    return { state: 'cancelled', request_id: requestId }
  },
}
