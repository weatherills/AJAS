import { describe, expect, it } from 'vitest'
import {
  counterfactual,
  enJobsLabel,
  missingMustHaves,
  phoneLayout,
  searchNormalized,
  sprint14Changelog,
  subScores,
  toastDigest,
  wcagName,
} from './sprint14'

describe('sprint14 helpers', () => {
  it('suggests missing skills and sub-scores', () => {
    expect(counterfactual(['Python'], ['Python', 'Go']).add).toEqual(['Go'])
    expect(missingMustHaves(['Python'], ['Python', 'SQL'])).toEqual(['SQL'])
    expect(subScores(1, 1, 1).total).toBe(1)
  })

  it('searches normalized JD fields and formats a11y/i18n', () => {
    expect(searchNormalized([{ title: 'Staff Python', company: 'Acme' }], 'python')).toHaveLength(1)
    expect(wcagName('list')['aria-label']).toBe('Job results')
    expect(enJobsLabel()).toBe('Jobs')
    expect(phoneLayout(390)).toBe(true)
    expect(toastDigest(['a', 'b']).count).toBe(2)
    expect(sprint14Changelog()[0].version).toBe('14.0.0')
  })
})
