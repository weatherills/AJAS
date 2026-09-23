/** Shared breakpoints for core AJAS views (feed, filters, settings, nav). */
export const BREAKPOINTS = {
  phone: 640,
  tablet: 767,
  desktop: 1024,
} as const

export type LayoutMode = 'phone' | 'tablet' | 'desktop'

export function layoutMode(width: number): LayoutMode {
  if (width <= BREAKPOINTS.phone) return 'phone'
  if (width <= BREAKPOINTS.tablet) return 'tablet'
  return 'desktop'
}

export function isPhoneLayout(width: number): boolean {
  return layoutMode(width) === 'phone'
}

/** Job Feed PRD: mobile sheet <768, filter rail ≥768, list+drawer split ≥1024. */
export type FeedChrome = 'sheet' | 'rail' | 'split'

export const FEED_RAIL_MIN = 768
export const FEED_SPLIT_MIN = 1024

export function feedChrome(width: number): FeedChrome {
  if (width < FEED_RAIL_MIN) return 'sheet'
  if (width < FEED_SPLIT_MIN) return 'rail'
  return 'split'
}
