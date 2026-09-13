import { describe, expect, it } from 'vitest'
import { chooseResume, loadApplyPrefs, saveApplyPrefs } from './applyPrefs'

describe('apply prefs resume chooser', () => {
  it('prefers the stored resume when it still exists', () => {
    saveApplyPrefs({ defaultCoverMode: 'none', location: '', coverTone: 'concise', defaultResumeId: 'r2' })
    expect(loadApplyPrefs().defaultResumeId).toBe('r2')
    expect(chooseResume([{ id: 'r1' }, { id: 'r2' }], 'r2')).toBe('r2')
    expect(chooseResume([{ id: 'r1' }], 'missing')).toBe('r1')
  })
})
