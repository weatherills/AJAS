import { describe, expect, it } from 'vitest'
import { redactDlq, retryDlq } from './dlq'

describe('dead letter queue', () => {
  it('redacts secrets and retries a row', () => {
    expect(redactDlq({ token: 'abc', title: 'Staff' })).toEqual({ token: '[redacted]', title: 'Staff' })
    const next = retryDlq([{ id: '1', payload: {}, status: 'dead' }], '1')
    expect(next[0].status).toBe('queued')
  })
})
