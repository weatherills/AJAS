import type { EmailStatus } from '../api/emailTypes'

export type ProviderHealth = {
  provider: string
  ok: boolean
  lastError: string | null
  reconnect: boolean
  label: string
}

export function emailProviderHealth(status: EmailStatus | null | undefined): ProviderHealth {
  const provider = status?.provider || (status?.graphConnected ? 'microsoft365' : 'demo')
  const lastError = status?.lastSyncError || null
  const configured = status?.oauthConfigured !== false
  const graph = Boolean(status?.graphConnected)
  const reconnect = !configured || Boolean(lastError) || (status?.connected === false && !status?.demo)
  return {
    provider,
    ok: graph && !lastError && configured,
    lastError,
    reconnect,
    label: graph ? 'Microsoft 365 healthy' : configured ? 'Demo mailbox' : 'OAuth not configured',
  }
}
