import { describe, expect, it } from 'vitest'
import { filtersFromSearch, filtersForTab } from './review'
import { reviewHref } from './routes'
import { onboardingSteps } from './onboarding'

describe('review shareable filters', () => {
  it('round-trips min/max/company/q into the hash', () => {
    const href = reviewHref({ min: 70, max: 90, company: 'Acme', q: 'staff', tab: 'saved' })
    expect(href).toContain('tab=saved')
    expect(href).toContain('min=70')
    expect(href).toContain('company=Acme')
    expect(href).toContain('q=staff')
    const params = new URLSearchParams(href.split('?')[1])
    const filters = filtersFromSearch(params, 'saved')
    expect(filters.minScore).toBe(70)
    expect(filters.company).toBe('Acme')
    expect(filters.q).toBe('staff')
  })

  it('keeps tab defaults when query is empty', () => {
    expect(filtersForTab('matches').source).toBe('ai')
    expect(filtersFromSearch(new URLSearchParams(), 'history').status).toBe('all')
  })
})

describe('onboarding checklist', () => {
  it('marks remaining work until every step is done', () => {
    const steps = onboardingSteps({
      emailConnected: true,
      sourceEnabled: false,
      thresholdSet: true,
      reviewed: false,
    })
    expect(steps.filter((item) => item.done).map((item) => item.id)).toEqual(['email', 'threshold'])
    expect(steps.find((item) => item.id === 'review')?.href).toBe('#/review')
  })
})
