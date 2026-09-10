export type NavLink = { href: string; label: string }

export const NAV_LINKS: NavLink[] = [
  { href: '#/', label: 'Home' },
  { href: '#/resumes', label: 'Resumes' },
  { href: '#/jobs', label: 'Jobs' },
  { href: '#/review', label: 'Review' },
  { href: '#/apply', label: 'Apply' },
  { href: '#/email', label: 'Email' },
  { href: '#/learning', label: 'Learning' },
  { href: '#/settings', label: 'Settings' },
  { href: '#/ops', label: 'Ops' },
]

export function hashPath(hash: string): string {
  const raw = (hash.replace(/^#/, '') || '/').split('?')[0]
  return raw.startsWith('/') ? raw : `/${raw}`
}

export function navIsActive(href: string, hash: string): boolean {
  const path = hashPath(hash)
  const target = href.replace(/^#/, '') || '/'
  if (target === '/') return path === '/'
  return path === target || path.startsWith(`${target}/`)
}
