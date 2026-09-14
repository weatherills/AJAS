import { describe, expect, it } from 'vitest'
import { enJobsLabel, phraseSearch, skipLinks, sprint16Changelog, swipeActions, wcagName } from './sprint16'

describe('sprint16 helpers', () => {
  it('parses phrase and NOT search', () => {
    expect(phraseSearch([{ title: 'Staff Python', company: 'Acme' }, { title: 'Java Python', company: 'Beta' }], '"staff python" NOT java')).toHaveLength(1)
    expect(skipLinks().main).toBe('#main')
  })

  it('formats a11y/i18n and changelog', () => {
    expect(wcagName('list')['aria-label']).toBe('Job results')
    expect(enJobsLabel()).toBe('Jobs')
    expect(swipeActions(390).enabled).toBe(true)
    expect(sprint16Changelog()[0].version).toBe('16.0.0')
  })
})
