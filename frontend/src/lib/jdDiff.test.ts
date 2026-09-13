import { describe, expect, it } from 'vitest'
import { unifiedDiff } from './jdDiff'

describe('job description diff', () => {
  it('emits added and removed lines when a JD updates', () => {
    const diff = unifiedDiff('Build crawlers.\nOwn ranking.', 'Build crawlers.\nOwn ranking and explanations.')
    expect(diff.changed).toBe(true)
    expect(diff.lines.some((line) => line.startsWith('- '))).toBe(true)
    expect(diff.lines.some((line) => line.startsWith('+ '))).toBe(true)
  })
})
