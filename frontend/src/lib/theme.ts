export type ThemePref = 'dark' | 'light' | 'system'
export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'ajas.theme'

export function readThemePref(): ThemePref {
  try {
    const value = globalThis.localStorage?.getItem(STORAGE_KEY)
    if (value === 'dark' || value === 'light' || value === 'system') return value
  } catch {
    /* ignore */
  }
  return 'system'
}

export function resolveTheme(pref: ThemePref, systemDark: boolean): Theme {
  if (pref === 'system') return systemDark ? 'dark' : 'light'
  return pref
}

export function applyTheme(theme: Theme): void {
  const root = globalThis.document?.documentElement
  if (!root) return
  root.dataset.theme = theme
  root.style.colorScheme = theme
}

export function setThemePref(pref: ThemePref, systemDark = true): Theme {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, pref)
  } catch {
    /* ignore */
  }
  const theme = resolveTheme(pref, systemDark)
  applyTheme(theme)
  return theme
}

export function cycleTheme(pref: ThemePref): ThemePref {
  if (pref === 'system') return 'dark'
  if (pref === 'dark') return 'light'
  return 'system'
}
