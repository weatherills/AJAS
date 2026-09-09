import { liveReviewApi } from './reviewLive'
import { mockReviewApi } from './reviewMock'
import { liveAutoApplyApi } from './autoApplyLive'
import { mockAutoApplyApi } from './autoApplyMock'
import type { ReviewApi } from './reviewTypes'
import type { AutoApplyApi } from './autoApplyTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const reviewApi: ReviewApi = USE_MOCK ? mockReviewApi : liveReviewApi
export const autoApplyApi: AutoApplyApi = USE_MOCK ? mockAutoApplyApi : liveAutoApplyApi

export { getUserId, setUserId } from './live'
export type { ReviewApi, ReviewMatch } from './reviewTypes'
export type { AutoApplyApi } from './autoApplyTypes'
