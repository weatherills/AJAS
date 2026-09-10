import { ApiError } from '../api/live'

export function describeApiError(err: unknown): { message: string; retryable: boolean; retryAfter: number | null } {
  if (err instanceof ApiError) {
    if (err.code === 'RATE_LIMITED' || err.status === 429) {
      return {
        message: err.retryAfter
          ? `Too many requests. Try again in ${err.retryAfter}s.`
          : 'Too many requests. Wait a moment and retry.',
        retryable: true,
        retryAfter: err.retryAfter,
      }
    }
    return { message: err.message, retryable: err.retryable || err.status >= 500, retryAfter: err.retryAfter }
  }
  if (err instanceof Error) return { message: err.message, retryable: false, retryAfter: null }
  return { message: 'Something went wrong', retryable: false, retryAfter: null }
}
