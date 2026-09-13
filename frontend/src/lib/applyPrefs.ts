const KEY = 'ajas.apply.prefs'

export type ApplyPrefs = {
  defaultCoverMode: 'none' | 'upload' | 'generate'
  location: string
}

export function loadApplyPrefs(): ApplyPrefs {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { defaultCoverMode: 'none', location: '' }
    const parsed = JSON.parse(raw) as Partial<ApplyPrefs>
    const mode = parsed.defaultCoverMode
    return {
      defaultCoverMode: mode === 'upload' || mode === 'generate' ? mode : 'none',
      location: typeof parsed.location === 'string' ? parsed.location : '',
    }
  } catch {
    return { defaultCoverMode: 'none', location: '' }
  }
}

export function saveApplyPrefs(prefs: ApplyPrefs): void {
  localStorage.setItem(KEY, JSON.stringify(prefs))
}
