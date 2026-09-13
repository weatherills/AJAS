import { localeTag, type Locale } from './i18n'

export function formatDate(iso: string, locale: Locale = 'en'): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(localeTag(locale), { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function formatNumber(value: number, locale: Locale = 'en'): string {
  return new Intl.NumberFormat(localeTag(locale)).format(value)
}

export function formatPercent(value: number, locale: Locale = 'en'): string {
  return new Intl.NumberFormat(localeTag(locale), { style: 'percent', maximumFractionDigits: 0 }).format(value)
}
