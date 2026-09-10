import { json, request } from './live'
import type { SettingsApi, SettingsDoc } from './settingsTypes'

export const liveSettingsApi: SettingsApi = {
  async get() {
    return json<SettingsDoc>(await request('/api/v1/settings'))
  },
  async patch(body) {
    return json<SettingsDoc>(
      await request('/api/v1/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async listAudit() {
    return json(await request('/api/v1/settings/audit'))
  },
  async connectEmail(redirectUri) {
    return json(
      await request('/api/v1/settings/email/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirectUri }),
      }),
    )
  },
  async emailCallback(body) {
    return json<SettingsDoc>(
      await request('/api/v1/settings/email/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
  async disconnectEmail() {
    return json<SettingsDoc>(await request('/api/v1/settings/email/disconnect', { method: 'POST' }))
  },
}
