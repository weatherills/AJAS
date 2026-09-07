import { liveApi } from './live'
import { mockApi, seedMockResume } from './mock'
import { liveJobsApi } from './jobsLive'
import { mockJobsApi } from './jobsMock'
import { liveSettingsApi } from './settingsLive'
import { mockSettingsApi } from './settingsMock'
import type { JobsApi } from './jobsTypes'
import type { SettingsApi } from './settingsTypes'
import type { ResumeApi } from './types'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const api: ResumeApi = USE_MOCK ? mockApi : liveApi

export const settingsApi: SettingsApi = USE_MOCK ? mockSettingsApi : liveSettingsApi

export const jobsApi: JobsApi = USE_MOCK ? mockJobsApi : liveJobsApi

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
