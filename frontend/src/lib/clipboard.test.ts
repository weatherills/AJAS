import { describe, expect, it } from 'vitest'
import { copyText, explanationClipboardPayload } from './clipboard'

describe('match explanation clipboard', () => {
  it('joins explanation, skills, and gaps', () => {
    const text = explanationClipboardPayload({
      explanation: 'Strong python overlap.',
      highlights: ['python', 'azure'],
      gaps: ['rust'],
    })
    expect(text).toContain('Strong python overlap.')
    expect(text).toContain('Skills: python, azure')
    expect(text).toContain('Gaps: rust')
  })

  it('returns false when clipboard is unavailable', async () => {
    expect(await copyText('hello')).toBe(false)
  })
})
