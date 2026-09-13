import { describe, expect, it } from 'vitest'
import { buildExportBundle, purgeSummary } from './privacy'

describe('privacy', () => {
  it('builds a GDPR export bundle', () => {
    const bundle = buildExportBundle('ada')
    expect(bundle.userId).toBe('ada')
    expect(bundle.jobs).toEqual([])
  })
})
