import { describe, expect, it } from 'vitest'
import { buildExportBundle, purgeSummary } from './privacy'

describe('privacy', () => {
  it('summarizes a right-to-be-forgotten purge', () => {
    expect(purgeSummary(buildExportBundle('ada'))).toEqual({ deleted: 0, userId: 'ada' })
  })
})
