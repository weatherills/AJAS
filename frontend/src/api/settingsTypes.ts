import type { EmailApiStatus } from '../lib/settings'

export type SettingsDoc = {
  matchThreshold: number
  oauthConfigured?: boolean
  autoApplyEnabled?: boolean
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
    greenhouseConfigured?: boolean
    leverConfigured?: boolean
  }
  audit: {
    createdAt: string
    updatedAt: string
    updatedBy: string
  }
}

export type SettingsAuditItem = {
  id: string
  entityType: string
  entityId: string
  actorId: string
  fieldMask: string[]
  detail: Record<string, unknown>
  createdAt: string
}

export type SettingsApi = {
  get(): Promise<SettingsDoc>
  patch(body: {
    matchThreshold?: number
    autoApplyEnabled?: boolean
    sources?: { greenhouseEnabled?: boolean; leverEnabled?: boolean }
  }): Promise<SettingsDoc>
  listAudit(): Promise<{ items: SettingsAuditItem[] }>
  connectEmail(redirectUri: string): Promise<{ authUrl: string | null; state: string | null; noOp: boolean }>
  emailCallback(body: { code: string; state: string; redirectUri: string }): Promise<SettingsDoc>
  disconnectEmail(): Promise<SettingsDoc>
}
