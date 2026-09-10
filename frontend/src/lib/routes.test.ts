import { describe, expect, it } from 'vitest'
import { applyHref, emailHref, hashHref, jobHref, parseHash, reviewHref } from './routes'

describe('hash routes', () => {
  it('parses path and query from the hash', () => {
    expect(parseHash('#/review?match=match-staff&pane=emails').path).toBe('/review')
    expect(parseHash('#/review?match=match-staff&pane=emails').params.get('match')).toBe('match-staff')
    expect(parseHash('#/review?match=match-staff&pane=emails').params.get('pane')).toBe('emails')
    expect(parseHash('').path).toBe('/')
  })

  it('builds job, review, email, and apply hrefs', () => {
    expect(jobHref('job-1', 'emails')).toBe('#/jobs?job=job-1&tab=emails')
    expect(reviewHref({ matchId: 'match-staff', pane: 'emails' })).toBe('#/review?match=match-staff&pane=emails')
    expect(reviewHref({ jobId: 'job-1' })).toBe('#/review?job=job-1')
    expect(emailHref({ jobId: 'job-1', threadId: 't-staff' })).toBe('#/email?job=job-1&thread=t-staff')
    expect(applyHref('req-1', 'job-1')).toBe('#/apply/req-1?job=job-1')
    expect(hashHref('/settings')).toBe('#/settings')
  })

  it('omits empty query values', () => {
    expect(reviewHref({ matchId: 'match-staff', jobId: 'job-1' })).toBe('#/review?match=match-staff')
    expect(emailHref({})).toBe('#/email')
  })
})
