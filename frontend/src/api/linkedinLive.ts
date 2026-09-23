import { json, request } from './live'
import type { JobCard } from './jobsTypes'
import { linkedinListingToCard, type LinkedInListing } from '../lib/linkedin'

export type LinkedInSearchBody = {
  live?: boolean
  keywords?: string
  q?: string
  location?: string
  locations?: string[]
  workplace?: string
  accountId?: string
  payload?: unknown
}

export type LinkedInSearchResult = {
  jobs: JobCard[]
  reason: string
  liveFetch?: boolean
  bypass?: boolean
  userPrompt?: string
}

export type LinkedInSessionAccount = {
  accountId: string
  status: string
  remainingSeconds?: number
  tokenHash?: string
}

export type LinkedInEasyApplyBody = {
  job: Record<string, unknown>
  profile: Record<string, string>
  questions?: Record<string, string> | { id?: string; prompt?: string; key?: string; answer?: string }[]
  attachments?: { kind: string; name: string; contentType: string; size?: number; data?: string }[]
  accountId?: string
  live?: boolean
}

export type LinkedInEasyApplyResult = {
  status: string
  reason?: string
  code?: string
  userPrompt?: string
  hitl?: boolean
  abort?: boolean
  bypass?: boolean
  liveFetch?: boolean
  receipt?: { receiptId?: string; confirmation?: string; status?: string }
}

export type LinkedInStatus = {
  flags?: { linkedin_adapter?: boolean; linkedin_easy_apply?: boolean }
  linkedinLive?: boolean
  linkedinAccounts?: LinkedInSessionAccount[]
}

export const liveLinkedInApi = {
  async status() {
    return json<LinkedInStatus>(await request('/api/v1/integrations/status'))
  },
  async search(body: LinkedInSearchBody): Promise<LinkedInSearchResult> {
    const data = await json<{ jobs?: LinkedInListing[]; reason?: string; liveFetch?: boolean; bypass?: boolean; userPrompt?: string }>(
      await request('/api/v1/integrations/linkedin/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
    const jobs = (data.jobs || []).map(linkedinListingToCard)
    return {
      jobs,
      reason: String(data.reason || 'ok'),
      liveFetch: data.liveFetch,
      bypass: data.bypass,
      userPrompt: data.userPrompt,
    }
  },
  async easyApply(body: LinkedInEasyApplyBody) {
    return json<LinkedInEasyApplyResult>(
      await request('/api/v1/integrations/linkedin/easy-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async listSessions() {
    return json<{ accounts: LinkedInSessionAccount[] }>(await request('/api/v1/integrations/linkedin/session'))
  },
  async putSession(accountId: string, token: string) {
    return json<LinkedInSessionAccount>(
      await request('/api/v1/integrations/linkedin/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId, token }),
      }),
    )
  },
  async refreshSession(accountId: string, token?: string) {
    return json<LinkedInSessionAccount>(
      await request('/api/v1/integrations/linkedin/session/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId, token }),
      }),
    )
  },
  async revokeSession(accountId: string) {
    return json<LinkedInSessionAccount>(
      await request('/api/v1/integrations/linkedin/session/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId }),
      }),
    )
  },
}
