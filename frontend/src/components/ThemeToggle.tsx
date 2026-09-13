import { cycleTheme, readThemePref, setThemePref, type ThemePref } from '../lib/theme'
import { t } from '../lib/i18n'
import { useState } from 'react'

export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(() => readThemePref())
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={t('darkMode')}
      onClick={() => {
        const next = cycleTheme(pref)
        setPref(next)
        setThemePref(next, globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true)
      }}
    >
      {pref}
    </button>
  )
}
