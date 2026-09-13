import { describe, expect, it } from 'vitest'
import { expandedAttr, skipLink } from './a11y'

describe('accessibility helpers', () => {
  it('exposes a skip link and filter expanded state', () => {
    expect(skipLink()).toEqual({ href: '#ajas-main', label: 'Skip to content' })
    expect(expandedAttr(true)['aria-expanded']).toBe(true)
  })
})
