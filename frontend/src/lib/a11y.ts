export function skipLink(): { href: string; label: string } {
  return { href: '#ajas-main', label: 'Skip to content' }
}

export function expandedAttr(open: boolean): { 'aria-expanded': boolean; 'aria-controls': string } {
  return { 'aria-expanded': open, 'aria-controls': 'ajas-filters' }
}
