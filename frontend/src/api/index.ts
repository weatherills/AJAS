import { liveApi } from './live'
import { mockApi, seedMockResume } from './mock'
import { liveJobsApi } from './jobsLive'
import { mockJobsApi } from './jobsMock'
import { liveMatchingApi } from './matchingLive'
import { mockMatchingApi } from './matchingMock'
import { liveSettingsApi } from './settingsLive'
import { mockSettingsApi } from './settingsMock'
import type { JobsApi } from './jobsTypes'
import type { MatchingApi } from './matchingTypes'
import type { SettingsApi } from './settingsTypes'
import type { ResumeApi } from './types'
import { liveReviewApi } from './reviewLive'
import { mockReviewApi } from './reviewMock'
import type { ReviewApi } from './reviewTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const api: ResumeApi = USE_MOCK ? mockApi : liveApi

export const settingsApi: SettingsApi = USE_MOCK ? mockSettingsApi : liveSettingsApi

export const jobsApi: JobsApi = USE_MOCK ? mockJobsApi : liveJobsApi

export const matchingApi: MatchingApi = USE_MOCK ? mockMatchingApi : liveMatchingApi

export const reviewApi: ReviewApi = USE_MOCK ? mockReviewApi : liveReviewApi

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
export type { SettingsApi, SettingsDoc } from './settingsTypes'
export type { JobCard, JobsApi } from './jobsTypes'
export type { MatchView, MatchingApi } from './matchingTypes'
export type { ReviewApi, ReviewMatch } from './reviewTypes'
