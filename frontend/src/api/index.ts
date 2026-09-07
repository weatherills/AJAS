import { liveApi } from './live'
import { mockApi, seedMockResume } from './mock'
import type { ResumeApi } from './types'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const api: ResumeApi = USE_MOCK ? mockApi : liveApi

if (USE_MOCK) {
  seedMockResume()
  seedMockResume({
    id: 'seed-failed',
    fileName: 'needs-work.pdf',
    status: 'parse_failed',
    validated: false,
    lastParseError: 'Could not read this file',
    skills: [],
    experience: [],
    education: [],
    contact: { fullName: '' },
    fileHash: 'def456',
  })
}

export { getUserId, setUserId } from './live'
export type { ResumeApi, ResumeDetail, ResumeListItem } from './types'
