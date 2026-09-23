import { describe, expect, it } from 'vitest'
import { linkedinListingToCard, linkedinStatusRow, loadLinkedInAccountId, saveLinkedInAccountId } from './linkedin'

describe('linkedin helpers', () => {
  it('maps a guest listing onto a JobCard without adding LinkedIn to cosmos SOURCE_TYPES', () => {
    const card = linkedinListingToCard({
      id: '4123456789',
      title: 'Staff Platform Engineer',
      company: 'Initech',
      location: 'Remote, United States',
      postingUrl: 'https://www.linkedin.com/jobs/view/4123456789',
      applyMethod: 'easy_apply',
      postedAt: '2026-03-01',
    })
    expect(card.primarySource).toBe('linkedin')
    expect(card.sources[0].source).toBe('linkedin')
    expect(card.applyMethod).toBe('easy_apply')
    expect(card.applyUrl).toContain('linkedin.com/jobs/view')
  })

  it('stores the operator account id locally and reports live-off without marking the source unconfigured', () => {
    expect(saveLinkedInAccountId('acct-live')).toBe('acct-live')
    expect(loadLinkedInAccountId()).toBe('acct-live')
    const row = linkedinStatusRow({ adapterOn: true, live: false, accounts: [] })
    expect(row.source).toBe('linkedin')
    expect(row.configured).toBe(true)
    expect(row.status).toBe('ok')
    expect(row.errorMessage).toMatch(/LINKEDIN_LIVE/)
    const off = linkedinStatusRow({ adapterOn: false })
    expect(off.configured).toBe(false)
    expect(off.status).toBe('unconfigured')
  })
})
