import { describe, expect, it } from 'vitest'
import { availableLocales, currentLocale, setLocale, t } from './i18n'

describe('i18n', () => {
  it('returns English base strings and accepts fr/es', () => {
    setLocale('en')
    expect(availableLocales()).toEqual(['en', 'fr', 'es'])
    expect(t('jobs')).toBe('Jobs')
    expect(t('settings')).toBe('Settings')
    expect(t('language')).toBe('Language')
    expect(currentLocale()).toBe('en')
    expect(setLocale('fr')).toBe('fr')
    expect(t('jobs')).toBe('Offres')
    setLocale('en')
  })
})
