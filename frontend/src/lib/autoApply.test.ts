import { describe, expect, it } from 'vitest'
import { mockAutoApplyApi, resetAutoApplyMock } from '../api/autoApplyMock'
import { canCancel, defaultPostingUrl, inferJobSource, stateLabel } from './autoApply'

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
  })
})
