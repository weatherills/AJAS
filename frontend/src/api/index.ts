import { liveReviewApi } from './reviewLive'
import { mockReviewApi } from './reviewMock'
import { liveAutoApplyApi } from './autoApplyLive'
import { mockAutoApplyApi } from './autoApplyMock'
import { liveSettingsApi } from './settingsLive'
import { mockSettingsApi } from './settingsMock'
import { liveResumeApi } from './resumeLive'
import { mockApi as mockResumeApi, seedMockResume } from './resumeMock'
import { liveJobsApi } from './jobsLive'
import { mockJobsApi } from './jobsMock'
import { liveMatchingApi } from './matchingLive'
import { mockMatchingApi } from './matchingMock'
import { liveEmailApi } from './emailLive'
import { mockEmailApi } from './emailMock'
import { liveLearningApi } from './learningLive'
import { mockLearningApi } from './learningMock'
import type { ReviewApi } from './reviewTypes'
import type { AutoApplyApi } from './autoApplyTypes'
import type { SettingsApi } from './settingsTypes'
import type { ResumeApi } from './resumeTypes'
import type { JobsApi } from './jobsTypes'
import type { MatchingApi } from './matchingTypes'
import type { EmailApi } from './emailTypes'
import type { LearningApi } from './learningTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const reviewApi: ReviewApi = USE_MOCK ? mockReviewApi : liveReviewApi
export const autoApplyApi: AutoApplyApi = USE_MOCK ? mockAutoApplyApi : liveAutoApplyApi
export const settingsApi: SettingsApi = USE_MOCK ? mockSettingsApi : liveSettingsApi
export const resumeApi: ResumeApi = USE_MOCK ? mockResumeApi : liveResumeApi
export const jobsApi: JobsApi = USE_MOCK ? mockJobsApi : liveJobsApi
export const matchingApi: MatchingApi = USE_MOCK ? mockMatchingApi : liveMatchingApi
export const emailApi: EmailApi = USE_MOCK ? mockEmailApi : liveEmailApi
export const learningApi: LearningApi = USE_MOCK ? mockLearningApi : liveLearningApi

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
export type { JobCard, JobsApi } from './jobsTypes'
export type { MatchView, MatchingApi } from './matchingTypes'
export type { EmailApi, EmailThread } from './emailTypes'
export type { LearningApi } from './learningTypes'
