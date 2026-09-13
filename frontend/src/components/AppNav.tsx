import { skipLink } from '../lib/a11y'
import { NAV_LINKS, navIsActive } from '../lib/nav'
import { BOTTOM_NAV, swipeNav } from '../lib/sprint13'
import { ThemeToggle } from './ThemeToggle'

export function AppNav() {
  const hash = typeof window === 'undefined' ? '#/' : window.location.hash || '#/'
  const skip = skipLink()
  return (
    <>
      <a className="skip-link" href={skip.href}>
        {skip.label}
      </a>
      <nav className="app-nav" aria-label="AJAS">
      <span className="app-nav-links">
      {NAV_LINKS.map((link) => (
        <a key={link.href} href={link.href} className={navIsActive(link.href, hash) ? 'is-active' : undefined}>
          {link.label}
        </a>
      ))}
      </span>
      <ThemeToggle />
      </nav>
      <nav
        className="bottom-nav"
        aria-label="Primary"
        onTouchEnd={(event) => {
          const touch = event.changedTouches[0]
          const start = Number((event.currentTarget as HTMLElement).dataset.startX || 0)
          if (!touch || !start) return
          const next = swipeNav(touch.clientX - start, BOTTOM_NAV.map((item) => item.href), hash)
          if (next) window.location.hash = next
        }}
        onTouchStart={(event) => {
          const touch = event.touches[0]
          if (touch) (event.currentTarget as HTMLElement).dataset.startX = String(touch.clientX)
        }}
      >
        {BOTTOM_NAV.map((link) => (
          <a key={link.href} href={link.href} className={navIsActive(link.href, hash) ? 'is-active' : undefined}>
            {link.label}
          </a>
        ))}
      </nav>
    </>
  )
}
