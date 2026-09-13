import { describe, expect, it } from 'vitest'
import { bulkDismiss, dismissSnackbar, undoDismiss } from './dismiss'

describe('bulk dismiss', () => {
  it('removes selected jobs and restores them on undo', () => {
    const snap = bulkDismiss(['a', 'b', 'c'], ['b', 'c'])
    expect(snap.remaining).toEqual(['a'])
    expect(dismissSnackbar(snap.dismissed.length)).toContain('2 jobs')
    expect(undoDismiss(snap, snap.remaining)).toEqual(['b', 'c', 'a'])
  })
})
