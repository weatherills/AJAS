import { liveReviewApi } from './reviewLive'
import { mockReviewApi } from './reviewMock'
import { liveAutoApplyApi } from './autoApplyLive'
import { mockAutoApplyApi } from './autoApplyMock'
import { liveSettingsApi } from './settingsLive'
import { mockSettingsApi } from './settingsMock'
import { liveResumeApi } from './resumeLive'
import { mockApi as mockResumeApi, seedMockResume } from './resumeMock'
import type { ReviewApi } from './reviewTypes'
import type { AutoApplyApi } from './autoApplyTypes'
import type { SettingsApi } from './settingsTypes'
import type { ResumeApi } from './resumeTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const reviewApi: ReviewApi = USE_MOCK ? mockReviewApi : liveReviewApi
export const autoApplyApi: AutoApplyApi = USE_MOCK ? mockAutoApplyApi : liveAutoApplyApi
export const settingsApi: SettingsApi = USE_MOCK ? mockSettingsApi : liveSettingsApi
export const resumeApi: ResumeApi = USE_MOCK ? mockResumeApi : liveResumeApi

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
export type { ReviewApi, ReviewMatch } from './reviewTypes'
export type { AutoApplyApi } from './autoApplyTypes'
export type { SettingsApi } from './settingsTypes'
export type { ResumeApi, ResumeDetail, ResumeListItem } from './resumeTypes'
