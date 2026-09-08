import { liveReviewApi } from './reviewLive'
import { mockReviewApi } from './reviewMock'
import type { ReviewApi } from './reviewTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const reviewApi: ReviewApi = USE_MOCK ? mockReviewApi : liveReviewApi

export { getUserId, setUserId } from './live'
export type { ReviewApi, ReviewMatch } from './reviewTypes'
