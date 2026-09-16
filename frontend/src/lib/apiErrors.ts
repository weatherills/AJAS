import { ApiError } from '../api/live'

export const ERROR_REMEDIATION: Record<string, string> = {
  RATE_LIMITED: 'Wait for the retry window, then send fewer requests.',
  UNAVAILABLE: 'Check Azure Functions and Cosmos, then retry.',
  INGESTION_FAILED: 'Inspect source flags, robots/consent, and the circuit breaker.',
  SOURCE_NOT_CONFIGURED: 'Add a Greenhouse token or Lever URL in Settings.',
}

export function remediationFor(code: string | undefined, status: number): string {
  if (code && ERROR_REMEDIATION[code]) return ERROR_REMEDIATION[code]
  if (status === 401) return 'Sign in again or paste a valid session token.'
  if (status >= 500) return 'Retry shortly. If it persists, open Ops traces.'
  return 'Fix the request and try again.'
}

export function describeApiError(err: unknown): { message: string; retryable: boolean; retryAfter: number | null; remediation: string } {
  if (err instanceof ApiError) {
    if (err.code === 'RATE_LIMITED' || err.status === 429) {
      return {
        message: err.retryAfter
          ? `Too many requests. Try again in ${err.retryAfter}s.`
          : 'Too many requests. Wait a moment and retry.',
        retryable: true,
        retryAfter: err.retryAfter,
        remediation: remediationFor('RATE_LIMITED', err.status),
      }
    }
    return {
      message: err.message,
      retryable: err.retryable || err.status >= 500,
      retryAfter: err.retryAfter,
      remediation: remediationFor(err.code ?? undefined, err.status),
    }
  }
  if (err instanceof Error) return { message: err.message, retryable: false, retryAfter: null, remediation: 'Fix the request and try again.' }
  return { message: 'Something went wrong', retryable: false, retryAfter: null, remediation: 'Retry or contact support.' }
}
