import type { EmailApiStatus } from '../lib/settings'

export type SettingsDoc = {
  matchThreshold: number
  oauthConfigured?: boolean
  emailConnection: {
    status: EmailApiStatus
    provider: string | null
    tenantId: string | null
    accountId: string | null
    scopes: string[]
    lastVerifiedAt: string | null
    errorCode?: string | null
  }
  sources: {
    greenhouseEnabled: boolean
    leverEnabled: boolean
  }
  audit: {
    createdAt: string
    updatedAt: string
    updatedBy: string
  }
}

export type SettingsApi = {
  get(): Promise<SettingsDoc>
  patch(body: {
    matchThreshold?: number
    sources?: { greenhouseEnabled?: boolean; leverEnabled?: boolean }
  }): Promise<SettingsDoc>
  connectEmail(redirectUri: string): Promise<{ authUrl: string | null; state: string | null; noOp: boolean }>
  emailCallback(body: { code: string; state: string; redirectUri: string }): Promise<SettingsDoc>
  disconnectEmail(): Promise<SettingsDoc>
}
