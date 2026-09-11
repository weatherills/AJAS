import { describe, expect, it } from 'vitest'
import { mockAutoApplyApi, resetAutoApplyMock } from '../api/autoApplyMock'
import { canCancel, canMarkManualSubmitted, defaultPostingUrl, inferJobSource, stateLabel } from './autoApply'

describe('auto-apply helpers', () => {
  it('infers vendor from job id or posting URL', () => {
    expect(inferJobSource('job-staff', null)).toBe('greenhouse')
    expect(inferJobSource('job-lever', 'https://jobs.lever.co/acme/1')).toBe('lever')
    expect(inferJobSource('job-1', 'https://boards.greenhouse.io/acme/jobs/captcha')).toBe('manual')
  })

  it('builds a default posting URL and labels states', () => {
    expect(defaultPostingUrl('job-staff', 'greenhouse')).toContain('greenhouse')
    expect(stateLabel('rate_limited')).toBe('Rate limited')
    expect(stateLabel('submitted')).toBe('Submitted')
    expect(canCancel('queued')).toBe(true)
    expect(canCancel('submitted')).toBe(false)
    expect(canMarkManualSubmitted('packaged')).toBe(true)
    expect(canMarkManualSubmitted('submitted')).toBe(false)
  })
})

describe('mock auto-apply api', () => {
  it('submits greenhouse postings and packages captcha URLs', async () => {
    resetAutoApplyMock()
    const submitted = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-staff',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff',
      cover_letter_mode: 'none',
      consent_approved: true,
    })
    expect(submitted.state).toBe('submitted')
    const packaged = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-captcha',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/captcha',
      cover_letter_mode: 'none',
      consent_approved: true,
    })
    expect(packaged.state).toBe('packaged')
    const listed = await mockAutoApplyApi.list()
    expect(listed.items).toHaveLength(2)
    expect(listed.items[0].created_at).toBeTruthy()
    expect(listed.items[0].updated_at).toBeTruthy()
    const detail = await mockAutoApplyApi.get(submitted.request_id)
    expect(detail.created_at).toBeTruthy()
    expect(detail.updated_at).toBeTruthy()
  })

  it('stores a generated cover letter on the request', async () => {
    resetAutoApplyMock()
    const created = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-staff',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff',
      cover_letter_mode: 'generate',
      consent_approved: true,
    })
    const detail = await mockAutoApplyApi.get(created.request_id)
    expect(detail.cover_letter_source).toBe('ai')
    expect(detail.cover_letter_text).toMatch(/Alex Jobseeker/)
    expect(detail.artifacts.cover_letter_blob_sas).toBeTruthy()
  })

  it('uses apply-form answers for contact and generated cover letters', async () => {
    resetAutoApplyMock()
    const created = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-staff',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff',
      cover_letter_mode: 'generate',
      consent_approved: true,
      answers: { full_name: 'Jane Doe', email: 'jane@example.com' },
    })
    const detail = await mockAutoApplyApi.get(created.request_id)
    expect(detail.autofill.find((row) => row.field_key === 'full_name')?.value).toBe('Jane Doe')
    expect(detail.cover_letter_text).toMatch(/Jane Doe/)
  })

  it('stores an uploaded cover letter', async () => {
    resetAutoApplyMock()
    const created = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-staff',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff',
      cover_letter_mode: 'upload',
      cover_letter_text: 'Please consider my application.\nJane Doe',
      consent_approved: true,
    })
    const detail = await mockAutoApplyApi.get(created.request_id)
    expect(detail.cover_letter_source).toBe('upload')
    expect(detail.cover_letter_text).toMatch(/Jane Doe/)
  })

  it('requires pasted or uploaded cover letter text', async () => {
    resetAutoApplyMock()
    await expect(
      mockAutoApplyApi.create({
        job_source: 'greenhouse',
        job_posting_id: 'job-staff-empty-cover',
        posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff-empty-cover',
        cover_letter_mode: 'upload',
        cover_letter_text: '   ',
        consent_approved: true,
      }),
    ).rejects.toThrow(/cover_letter_text/)
  })

  it('marks a packaged attempt as manually submitted', async () => {
    resetAutoApplyMock()
    const packaged = await mockAutoApplyApi.create({
      job_source: 'manual',
      job_posting_id: 'job-manual',
      posting_url: 'https://jobs.example.com/apply',
      cover_letter_mode: 'none',
      consent_approved: true,
    })
    expect(packaged.state).toBe('packaged')
    const marked = await mockAutoApplyApi.markManualSubmitted(packaged.request_id)
    expect(marked.state).toBe('submitted')
    const detail = await mockAutoApplyApi.get(packaged.request_id)
    expect(detail.state).toBe('submitted')
    expect(detail.state_history.some((event) => event.event === 'manually_submitted')).toBe(true)
    await expect(mockAutoApplyApi.markManualSubmitted(packaged.request_id)).rejects.toThrow(/packaged/)
  })

  it('rejects marking an API-path greenhouse attempt as manually submitted', async () => {
    resetAutoApplyMock()
    const submitted = await mockAutoApplyApi.create({
      job_source: 'greenhouse',
      job_posting_id: 'job-staff',
      posting_url: 'https://boards.greenhouse.io/demo/jobs/job-staff',
      cover_letter_mode: 'none',
      consent_approved: true,
    })
    expect(submitted.state).toBe('submitted')
    expect(canMarkManualSubmitted(submitted.state)).toBe(false)
    await expect(mockAutoApplyApi.markManualSubmitted(submitted.request_id)).rejects.toThrow(/packaged/)
  })
})
