import { describe, expect, it } from 'vitest'
import { BREAKPOINTS, isPhoneLayout, layoutMode } from './responsive'

describe('responsive layout', () => {
  it('maps core view widths to phone/tablet/desktop', () => {
    expect(layoutMode(375)).toBe('phone')
    expect(layoutMode(BREAKPOINTS.phone)).toBe('phone')
    expect(layoutMode(700)).toBe('tablet')
    expect(layoutMode(BREAKPOINTS.tablet)).toBe('tablet')
    expect(layoutMode(1280)).toBe('desktop')
    expect(isPhoneLayout(390)).toBe(true)
    expect(isPhoneLayout(900)).toBe(false)
  })
})
