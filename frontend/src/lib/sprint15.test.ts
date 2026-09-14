import { describe, expect, it } from 'vitest'
import { booleanSearch, compactNav, enJobsLabel, shortcuts, sprint15Changelog, whyNot, wcagName } from './sprint15'

describe('sprint15 helpers', () => {
  it('parses boolean search and why-not explanations', () => {
    expect(booleanSearch([{ title: 'Staff Python', company: 'Acme' }], 'python AND acme')).toHaveLength(1)
    expect(whyNot(['Python'], ['Python', 'Go']).missing).toEqual(['Go'])
    expect(shortcuts().j).toBe('next')
  })

  it('formats a11y/i18n and changelog', () => {
    expect(wcagName('list')['aria-label']).toBe('Job results')
    expect(enJobsLabel()).toBe('Jobs')
    expect(compactNav(390)).toBe(true)
    expect(sprint15Changelog()[0].version).toBe('15.0.0')
  })
})
