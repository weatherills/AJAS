import { settingsApi } from '../api'
import { OAUTH_MESSAGE_TYPE } from './settings'

export function oauthRedirectUri() {
  return `${window.location.origin}/oauth-callback.html`
}

export class PopupBlockedError extends Error {
  constructor() {
    super('The Microsoft window was blocked. Allow popups, then retry.')
    this.name = 'PopupBlockedError'
  }
}

export function listenForOAuth(expectedState: string, timeoutMs = 5 * 60 * 1000) {
  return new Promise<{ code: string; state: string }>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup()
      reject(new Error('Microsoft sign-in timed out'))
    }, timeoutMs)
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      const data = event.data as {
        type?: string
        code?: string | null
        state?: string | null
        error?: string | null
      }
      if (data?.type !== OAUTH_MESSAGE_TYPE) return
      cleanup()
      if (data.error) {
        reject(new Error(data.error === 'access_denied' ? 'Microsoft consent was cancelled' : 'Microsoft sign-in failed'))
        return
      }
      if (!data.code || data.state !== expectedState) {
        reject(new Error('Microsoft sign-in returned an invalid state'))
        return
      }
      resolve({ code: data.code, state: data.state })
    }
    const cleanup = () => {
      window.clearTimeout(timer)
      window.removeEventListener('message', onMessage)
    }
    window.addEventListener('message', onMessage)
  })
}

export async function connectMicrosoftMailbox(): Promise<void> {
  const redirectUri = oauthRedirectUri()
  const started = await settingsApi.connectEmail(redirectUri)
  if (started.noOp) return
  if (!started.authUrl || !started.state) throw new Error('Microsoft sign-in did not return a URL')
  const popup = window.open(started.authUrl, 'ajas-ms-oauth', 'popup=yes,width=520,height=720')
  if (!popup) throw new PopupBlockedError()
  const result = await listenForOAuth(started.state)
  await settingsApi.emailCallback({ ...result, redirectUri })
}
