import { describe, expect, it } from 'vitest'
import { availableLocales, currentLocale, setLocale, t } from './i18n'

describe('i18n', () => {
  it('returns English base strings and ignores unknown locales', () => {
    expect(availableLocales()).toEqual(['en'])
    setLocale('en')
    expect(t('jobs')).toBe('Jobs')
    expect(t('settings')).toBe('Settings')
    expect(t('language')).toBe('Language')
    expect(currentLocale()).toBe('en')
    expect(setLocale('fr')).toBe('en')
    expect(currentLocale()).toBe('en')
  })
})
