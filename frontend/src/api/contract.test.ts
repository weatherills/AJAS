import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { liveAutoApplyApi } from './autoApplyLive'
import { liveEmailApi } from './emailLive'
import { liveMatchingApi } from './matchingLive'
import { liveReviewApi } from './reviewLive'

const root = join(dirname(fileURLToPath(import.meta.url)), '../../..')
const endpoints = JSON.parse(readFileSync(join(root, 'contracts/endpoints.json'), 'utf8')) as {
  path: string
  client: string
}[]

const liveSources = [
  readFileSync(join(root, 'frontend/src/api/reviewLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/matchingLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/autoApplyLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/emailLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/jobsLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/resumeLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/settingsLive.ts'), 'utf8'),
  readFileSync(join(root, 'frontend/src/api/learningLive.ts'), 'utf8'),
].join('\n')

describe('frontend live clients', () => {
  it('cover every contracted client path', () => {
    for (const row of endpoints) {
      if (row.client === 'n/a') continue
      const needle = row.path.replace(/\{[^}]+\}/g, '')
      expect(liveSources.includes(needle) || liveSources.includes(row.path)).toBe(true)
    }
  })

  it('exports typed domain clients', () => {
    expect(typeof liveReviewApi.list).toBe('function')
    expect(typeof liveMatchingApi.scoreMany).toBe('function')
    expect(typeof liveAutoApplyApi.list).toBe('function')
    expect(typeof liveEmailApi.status).toBe('function')
  })
})
