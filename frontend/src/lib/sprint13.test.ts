import { describe, expect, it } from 'vitest'
import { windowedRange } from './jobs'
import { TRIAGE_HELP, triageShortcut } from './triageKeys'
import {
  applyRedaction,
  BOTTOM_NAV,
  diffLineClass,
  explanationChips,
  gestureSwipe,
  shouldRefreshSearch,
  showBottomNav,
  sprint13Changelog,
  swipeNav,
  virtualWindow10k,
} from './sprint13'

describe('sprint13 helpers', () => {
  it('maps accept aliases and keeps dismiss', () => {
    expect(triageShortcut({ key: 'a' })).toBe('apply')
    expect(triageShortcut({ key: 'Enter' })).toBe('apply')
    expect(triageShortcut({ key: 'y' })).toBe('apply')
    expect(triageShortcut({ key: 'd' })).toBe('dismiss')
    expect(TRIAGE_HELP).toMatch(/accept/)
  })

  it('builds hover chips and colors diff lines', () => {
    expect(explanationChips(['Python'])[0]).toEqual({ label: 'Python', detail: 'Matched on Python' })
    expect(diffLineClass('+ added')).toContain('add')
    expect(diffLineClass('- removed')).toContain('del')
    expect(diffLineClass('+++ current')).not.toContain('add')
  })

  it('virtualizes a 10k job window', () => {
    const win = virtualWindow10k(10_000, 3600, 720)
    expect(win.virtualized).toBe(true)
    expect(win.end - win.start).toBeLessThan(200)
    expect(windowedRange(10_000, 0, 720).end).toBeLessThan(100)
  })

  it('refreshes stale saved searches and swipes bottom nav', () => {
    expect(shouldRefreshSearch(30, 15)).toEqual({ refresh: true, notify: true })
    expect(shouldRefreshSearch(5, 15).refresh).toBe(false)
    const hrefs = BOTTOM_NAV.map((item) => item.href)
    expect(swipeNav(-50, hrefs, '#/jobs')).toBe('#/review')
    expect(swipeNav(50, hrefs, '#/review')).toBe('#/jobs')
    expect(gestureSwipe(10, 80)).toBe('right')
    expect(showBottomNav(390)).toBe(true)
    expect(showBottomNav(1024)).toBe(false)
  })

  it('redacts configured fields and lists 13.0.0', () => {
    expect(applyRedaction({ email: 'a@b.c', title: 'Staff' }, ['email'])).toEqual({
      email: '[redacted]',
      title: 'Staff',
    })
    expect(sprint13Changelog()[0].version).toBe('13.0.0')
  })
})
