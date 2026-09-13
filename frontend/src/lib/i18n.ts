export const STRINGS = {
  en: {
    jobs: 'Jobs',
    filters: 'Filters',
    search: 'Search',
    apply: 'Apply',
    dismiss: 'Dismiss selected',
    settings: 'Settings',
    language: 'Language',
  },
} as const

export type Locale = keyof typeof STRINGS
export type MessageKey = keyof (typeof STRINGS)['en']

const STORAGE_KEY = 'ajas.locale'

function readStored(): Locale {
  try {
    const value = globalThis.localStorage?.getItem(STORAGE_KEY)
    if (value && value in STRINGS) return value as Locale
  } catch {
    /* private mode / tests */
  }
  return 'en'
}

let current: Locale = readStored()

export function setLocale(locale: string): Locale {
  current = locale in STRINGS ? (locale as Locale) : 'en'
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, current)
  } catch {
    /* ignore */
  }
  return current
}

export function t(key: MessageKey): string {
  return STRINGS[current][key] || STRINGS.en[key]
}

export function currentLocale(): Locale {
  return current
}

export function availableLocales(): Locale[] {
  return Object.keys(STRINGS) as Locale[]
}
