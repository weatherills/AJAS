/** LinkedIn extra-board search + Easy Apply helpers. Cosmos SOURCE_TYPES stay greenhouse|lever. */

import type { JobCard } from '../api/jobsTypes'
import { canonicalKey, sourceDomain } from './jobs'

export const LINKEDIN_ACCOUNT_KEY = 'ajas.linkedin.accountId'
export const DEFAULT_LINKEDIN_ACCOUNT = 'default'

const MEMORY = new Map<string, string>()

function readStore(key: string): string | null {
  try {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key)
  } catch {
    /* fall through */
  }
  return MEMORY.get(key) ?? null
}

function writeStore(key: string, value: string): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value)
      return
    }
  } catch {
    /* fall through */
  }
  MEMORY.set(key, value)
}

export function loadLinkedInAccountId(): string {
  return (readStore(LINKEDIN_ACCOUNT_KEY) || DEFAULT_LINKEDIN_ACCOUNT).trim() || DEFAULT_LINKEDIN_ACCOUNT
}

export function saveLinkedInAccountId(accountId: string): string {
  const next = accountId.trim() || DEFAULT_LINKEDIN_ACCOUNT
  writeStore(LINKEDIN_ACCOUNT_KEY, next)
  return next
}

export type LinkedInListing = {
  id?: string
  sourcePostingId?: string
  title?: string
  company?: string
  location?: string
  employmentType?: string
  description?: string
  postingUrl?: string
  applyUrl?: string
  applyMethod?: string
  externalApplyUrl?: string
  postedAt?: string
  canonicalKey?: string
  workplace?: string
  seniority?: string
  salaryMin?: number | null
  salaryMax?: number | null
}

export function linkedinListingToCard(job: LinkedInListing): JobCard {
  const url = String(job.postingUrl || job.applyUrl || '')
  const title = String(job.title || '')
  const company = String(job.company || '')
  const location = String(job.location || '')
  const id = String(job.id || job.sourcePostingId || url || title)
  const posted = String(job.postedAt || '') || new Date().toISOString()
  return {
    id,
    canonicalKey: String(job.canonicalKey || canonicalKey(title, location, company)),
    title,
    company,
    location,
    employmentType: String(job.employmentType || ''),
    snippet: String(job.description || '').slice(0, 160),
    applyUrl: url,
    updatedAt: posted,
    isNew: true,
    primarySource: 'linkedin',
    sources: [
      {
        source: 'linkedin',
        sourceUrl: url,
        postedAt: posted,
        domain: sourceDomain(url) || 'linkedin.com',
      },
    ],
    workplace: job.workplace,
    seniority: job.seniority,
    salaryMin: job.salaryMin ?? null,
    salaryMax: job.salaryMax ?? null,
    applyMethod: job.applyMethod,
    externalApplyUrl: job.externalApplyUrl,
  }
}

export function linkedinStatusRow(input: {
  adapterOn?: boolean
  easyApplyOn?: boolean
  live?: boolean
  accounts?: { accountId?: string; status?: string }[]
  lastSyncAt?: string | null
  reason?: string | null
}): {
  source: 'linkedin'
  status: 'ok' | 'error' | 'unconfigured'
  lastSyncAt: string | null
  backoffUntil: string | null
  errorMessage: string | null
  progress: string | null
  configured: boolean
  tenantCount: number
  boards: never[]
} {
  const adapterOn = input.adapterOn !== false
  const accounts = input.accounts || []
  const active = accounts.filter((item) => item.status === 'active' || item.status === 'expiring').length
  if (!adapterOn) {
    return {
      source: 'linkedin',
      status: 'unconfigured',
      lastSyncAt: input.lastSyncAt ?? null,
      backoffUntil: null,
      errorMessage: 'LinkedIn is turned off (FLAG_LINKEDIN_ADAPTER).',
      progress: null,
      configured: false,
      tenantCount: 0,
      boards: [],
    }
  }
  const liveOff = input.live === false
  const reason = input.reason || ''
  const error =
    reason === 'needs_manual'
      ? 'LinkedIn returned a checkpoint or CAPTCHA. Complete it in LinkedIn, then retry. AJAS never bypasses it.'
      : reason === 'live_disabled' || liveOff
        ? 'LinkedIn live sockets are off (LINKEDIN_LIVE). Guest search and Easy Apply stay fail-closed until it is on.'
        : reason === 'session_expired'
          ? 'Reconnect the LinkedIn account in Settings, then retry.'
          : null
  return {
    source: 'linkedin',
    status: error && reason === 'needs_manual' ? 'error' : 'ok',
    lastSyncAt: input.lastSyncAt ?? null,
    backoffUntil: null,
    errorMessage: error,
    progress: liveOff ? 'live off' : active ? `${active} session${active === 1 ? '' : 's'}` : 'guest search',
    configured: true,
    tenantCount: accounts.length,
    boards: [],
  }
}
