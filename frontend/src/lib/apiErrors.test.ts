import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/live'
import { describeApiError } from './apiErrors'

describe('describeApiError', () => {
  it('maps rate limits to a retry toast', () => {
    const err = new ApiError('slow', 429, 'RATE_LIMITED', true, 8)
    expect(describeApiError(err)).toEqual({
      message: 'Too many requests. Try again in 8s.',
      retryable: true,
      retryAfter: 8,
    })
  })
})
