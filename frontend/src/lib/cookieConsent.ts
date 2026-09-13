export type CookieChoices = {
  necessary: true
  analytics: boolean
  marketing: boolean
}

const STORAGE_KEY = 'ajas.cookies.v1'

export function defaultChoices(): CookieChoices {
  return { necessary: true, analytics: false, marketing: false }
}

export function readChoices(): CookieChoices | null {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<CookieChoices>
    return { necessary: true, analytics: Boolean(parsed.analytics), marketing: Boolean(parsed.marketing) }
  } catch {
    return null
  }
}

export function saveChoices(choices: CookieChoices): CookieChoices {
  const next = { ...choices, necessary: true as const }
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
  return next
}

export function bannerNeeded(): boolean {
  return readChoices() === null
}
