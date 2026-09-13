import { describe, expect, it } from 'vitest'
import { emailProviderHealth } from './emailHealth'

describe('email provider health', () => {
  it('asks to reconnect when Graph errors or OAuth is missing', () => {
    const healthy = emailProviderHealth({
      connected: true,
      graphConnected: true,
      address: 'ada@ajas.dev',
      lastSyncedAt: '2026-09-13T10:00:00Z',
      unreadCount: 0,
      demo: false,
      provider: 'microsoft365',
      oauthConfigured: true,
    })
    expect(healthy.ok).toBe(true)
    expect(healthy.reconnect).toBe(false)
    const broken = emailProviderHealth({
      connected: false,
      graphConnected: false,
      address: null,
      lastSyncedAt: null,
      unreadCount: 0,
      demo: false,
      lastSyncError: 'invalid_grant',
      oauthConfigured: true,
    })
    expect(broken.ok).toBe(false)
    expect(broken.reconnect).toBe(true)
  })
})
