import { skipLink } from '../lib/a11y'
import { NAV_LINKS, navIsActive } from '../lib/nav'
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
      {NAV_LINKS.map((link) => (
        <a key={link.href} href={link.href} className={navIsActive(link.href, hash) ? 'is-active' : undefined}>
          {link.label}
        </a>
      ))}
      <ThemeToggle />
      </nav>
    </>
  )
}
