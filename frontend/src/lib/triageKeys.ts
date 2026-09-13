export type TriageAction = 'next' | 'prev' | 'apply' | 'dismiss' | 'save' | 'why' | 'compare'

export function triageShortcut(event: {
  key: string
  metaKey?: boolean
  ctrlKey?: boolean
  altKey?: boolean
  target?: { tagName?: string } | null
}): TriageAction | null {
  const tag = (event.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return null
  if (event.metaKey || event.ctrlKey || event.altKey) return null
  switch (event.key.toLowerCase()) {
    case 'j':
      return 'next'
    case 'k':
      return 'prev'
    case 'a':
      return 'apply'
    case 'd':
      return 'dismiss'
    case 's':
      return 'save'
    case '?':
      return 'why'
    case 'c':
      return 'compare'
    default:
      return null
  }
}

export const TRIAGE_HELP = 'j/k move · a apply · d dismiss · s save · c compare · ? why'
