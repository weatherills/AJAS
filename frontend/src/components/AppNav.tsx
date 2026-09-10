import { NAV_LINKS, navIsActive } from '../lib/nav'

export function AppNav() {
  const hash = typeof window === 'undefined' ? '#/' : window.location.hash || '#/'
  return (
    <nav className="app-nav" aria-label="AJAS">
      {NAV_LINKS.map((link) => (
        <a key={link.href} href={link.href} className={navIsActive(link.href, hash) ? 'is-active' : undefined}>
          {link.label}
        </a>
      ))}
    </nav>
  )
}
