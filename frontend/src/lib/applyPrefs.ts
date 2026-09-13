const KEY = 'ajas.apply.prefs'
const MEMORY = new Map<string, string>()

export type CoverTone = 'concise' | 'enthusiastic' | 'formal'

export type ApplyPrefs = {
  defaultCoverMode: 'none' | 'upload' | 'generate'
  location: string
  coverTone: CoverTone
  defaultResumeId: string
}

const DEFAULT_PREFS: ApplyPrefs = { defaultCoverMode: 'none', location: '', coverTone: 'concise', defaultResumeId: '' }

function readStore(): string | null {
  try {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(KEY)
  } catch {
    /* fall through */
  }
  return MEMORY.get(KEY) ?? null
}

function writeStore(value: string): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(KEY, value)
      return
    }
  } catch {
    /* fall through */
  }
  MEMORY.set(KEY, value)
}

export function loadApplyPrefs(): ApplyPrefs {
  try {
    const raw = readStore()
    if (!raw) return { ...DEFAULT_PREFS }
    const parsed = JSON.parse(raw) as Partial<ApplyPrefs>
    const mode = parsed.defaultCoverMode
    const tone = parsed.coverTone
    return {
      defaultCoverMode: mode === 'upload' || mode === 'generate' ? mode : 'none',
      location: typeof parsed.location === 'string' ? parsed.location : '',
      coverTone: tone === 'enthusiastic' || tone === 'formal' ? tone : 'concise',
      defaultResumeId: typeof parsed.defaultResumeId === 'string' ? parsed.defaultResumeId : '',
    }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function saveApplyPrefs(prefs: ApplyPrefs): void {
  writeStore(JSON.stringify(prefs))
}

export function chooseResume(resumes: { id: string }[], preferred: string | null | undefined): string | null {
  if (preferred && resumes.some((item) => item.id === preferred)) return preferred
  return resumes[0]?.id || preferred || null
}
