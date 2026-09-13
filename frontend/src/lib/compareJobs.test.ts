import { describe, expect, it } from 'vitest'
import { compareRows, toggleCompareId } from './compareJobs'

describe('side-by-side job compare', () => {
  it('aligns score and employment fields', () => {
    const rows = compareRows(
      [
        { id: 'a', title: 'Staff', company: 'Acme', location: 'Remote', employmentType: 'full-time' },
        { id: 'b', title: 'Senior', company: 'Beta', location: 'NYC' },
      ],
      { a: { score: 82 }, b: { score: null } },
    )
    expect(rows[0].score).toBe(82)
    expect(rows[1].employmentType).toBe('')
  })

  it('caps compared jobs at three', () => {
    expect(toggleCompareId(['a', 'b', 'c'], 'd')).toEqual(['b', 'c', 'd'])
    expect(toggleCompareId(['a', 'b'], 'a')).toEqual(['b'])
  })
})
