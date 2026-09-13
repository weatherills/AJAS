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
