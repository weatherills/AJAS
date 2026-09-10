import type { SettingsApi, SettingsDoc } from './settingsTypes'

function now() {
  return new Date().toISOString()
}

function blank(): SettingsDoc {
  const stamp = now()
  return {
    matchThreshold: 0.7,
    oauthConfigured: true,
    emailConnection: {
      status: 'disconnected',
      provider: null,
      tenantId: null,
      accountId: null,
      scopes: [],
      lastVerifiedAt: null,
    },
    sources: { greenhouseEnabled: true, leverEnabled: true, greenhouseConfigured: true, leverConfigured: true },
    audit: { createdAt: stamp, updatedAt: stamp, updatedBy: 'local-user' },
  }
}

let doc = blank()
const oauth = new Map<string, { redirectUri: string }>()
let sourceExplicit = { greenhouse: false, lever: false }

function applySourceDefaults(next: SettingsDoc): SettingsDoc {
  const sources = { ...next.sources }
  if (!sourceExplicit.greenhouse) sources.greenhouseEnabled = sources.greenhouseConfigured !== false
  if (!sourceExplicit.lever) sources.leverEnabled = sources.leverConfigured !== false
  return { ...next, sources }
}

export function resetMockSettings() {
  doc = blank()
  oauth.clear()
  sourceExplicit = { greenhouse: false, lever: false }
}

export function markMockSourceConfigured(source: 'greenhouse' | 'lever', configured = true) {
  if (source === 'greenhouse') doc.sources.greenhouseConfigured = configured
  else doc.sources.leverConfigured = configured
  if (!configured) {
    if (source === 'greenhouse') doc.sources.greenhouseEnabled = false
    else doc.sources.leverEnabled = false
  } else if (source === 'greenhouse' && !sourceExplicit.greenhouse) {
    doc.sources.greenhouseEnabled = true
  } else if (source === 'lever' && !sourceExplicit.lever) {
    doc.sources.leverEnabled = true
  }
}

export const mockSettingsApi: SettingsApi = {
  async get() {
    return applySourceDefaults(structuredClone(doc))
  },
  async patch(body) {
    if (body.matchThreshold != null) doc.matchThreshold = body.matchThreshold
    if (body.sources?.greenhouseEnabled != null) {
      if (body.sources.greenhouseEnabled && doc.sources.greenhouseConfigured === false) {
        throw Object.assign(new Error('Greenhouse is not configured. Add a board token before turning this source on, or Job Feed stays empty.'), {
          code: 'SOURCE_NOT_CONFIGURED',
        })
      }
      doc.sources.greenhouseEnabled = body.sources.greenhouseEnabled
      sourceExplicit.greenhouse = true
    }
    if (body.sources?.leverEnabled != null) {
      if (body.sources.leverEnabled && doc.sources.leverConfigured === false) {
        throw Object.assign(new Error('Lever is not configured. Add a board token before turning this source on, or Job Feed stays empty.'), {
          code: 'SOURCE_NOT_CONFIGURED',
        })
      }
      doc.sources.leverEnabled = body.sources.leverEnabled
      sourceExplicit.lever = true
    }
    doc.audit.updatedAt = now()
    return applySourceDefaults(structuredClone(doc))
  },
  async connectEmail(redirectUri) {
    if (doc.emailConnection.status === 'connected') {
      return { authUrl: null, state: null, noOp: true }
    }
    const state = crypto.randomUUID()
    oauth.set(state, { redirectUri })
    doc.emailConnection = {
      ...doc.emailConnection,
      status: 'pending',
      provider: 'microsoft',
    }
    const authUrl = `${redirectUri}?code=mock-code&state=${encodeURIComponent(state)}`
    return { authUrl, state, noOp: false }
  },
  async emailCallback(body) {
    const session = oauth.get(body.state)
    if (!session || session.redirectUri !== body.redirectUri) {
      throw new Error('Invalid or expired OAuth state')
    }
    if (body.code === 'deny') {
      doc.emailConnection = {
        ...doc.emailConnection,
        status: 'error',
        errorCode: 'access_denied',
      }
      throw new Error('Microsoft consent was cancelled')
    }
    doc.emailConnection = {
      status: 'connected',
      provider: 'microsoft',
      tenantId: 'mock-tenant',
      accountId: 'jane@contoso.com',
      scopes: ['offline_access', 'Mail.Read'],
      lastVerifiedAt: now(),
      errorCode: null,
    }
    doc.audit.updatedAt = now()
    oauth.delete(body.state)
    return applySourceDefaults(structuredClone(doc))
  },
  async disconnectEmail() {
    doc.emailConnection = {
      status: 'disconnected',
      provider: null,
      tenantId: null,
      accountId: null,
      scopes: [],
      lastVerifiedAt: null,
    }
    doc.audit.updatedAt = now()
    return applySourceDefaults(structuredClone(doc))
  },
}
