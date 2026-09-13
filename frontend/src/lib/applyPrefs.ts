const KEY = 'ajas.apply.prefs'

export type CoverTone = 'concise' | 'enthusiastic' | 'formal'

export type ApplyPrefs = {
  defaultCoverMode: 'none' | 'upload' | 'generate'
  location: string
  coverTone: CoverTone
}

const DEFAULT_PREFS: ApplyPrefs = { defaultCoverMode: 'none', location: '', coverTone: 'concise' }

export function loadApplyPrefs(): ApplyPrefs {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { ...DEFAULT_PREFS }
    const parsed = JSON.parse(raw) as Partial<ApplyPrefs>
    const mode = parsed.defaultCoverMode
    const tone = parsed.coverTone
    return {
      defaultCoverMode: mode === 'upload' || mode === 'generate' ? mode : 'none',
      location: typeof parsed.location === 'string' ? parsed.location : '',
      coverTone: tone === 'enthusiastic' || tone === 'formal' ? tone : 'concise',
    }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function saveApplyPrefs(prefs: ApplyPrefs): void {
  localStorage.setItem(KEY, JSON.stringify(prefs))
}
