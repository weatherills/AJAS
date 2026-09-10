/** Map Settings Backend JSON (0.10–0.99) to the Frontend PRD slider (0–100). */

export const SLIDER_MIN = 0
export const SLIDER_MAX = 100
export const SLIDER_STEP = 1
export const DEFAULT_PERCENT = 70
export const API_MIN = 0.1
export const API_MAX = 0.99

export type EmailApiStatus = 'disconnected' | 'pending' | 'connected' | 'error'

export type EmailUiState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'action_required'
  | 'error'
  | 'unconfigured'

export const OAUTH_NOT_CONFIGURED = 'OAUTH_NOT_CONFIGURED'
export const SOURCE_NOT_CONFIGURED = 'SOURCE_NOT_CONFIGURED'

export function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_PERCENT
  return Math.min(SLIDER_MAX, Math.max(SLIDER_MIN, Math.round(value)))
}

export function percentToApi(percent: number): number {
  const clamped = clampPercent(percent)
  const asApi = Math.round(clamped) / 100
  return Math.min(API_MAX, Math.max(API_MIN, asApi))
}

export function apiToPercent(threshold: number | null | undefined): number {
  if (threshold == null || !Number.isFinite(threshold)) return DEFAULT_PERCENT
  return clampPercent(threshold * 100)
}

export function previewCopy(percent: number): string {
  if (percent >= 70) return 'Fewer matches'
  return 'More matches'
}

export function emailUiState(
  status: EmailApiStatus,
  errorCode?: string | null,
  connecting = false,
  oauthConfigured = true,
): EmailUiState {
  if (connecting || status === 'pending') return 'connecting'
  if (status === 'connected') return 'connected'
  if (!oauthConfigured) return 'unconfigured'
  if (status === 'error' && (errorCode === 'expired' || errorCode === 'revoked')) return 'action_required'
  if (status === 'error') return 'error'
  return 'disconnected'
}

export function oauthIsConfigured(value: boolean | null | undefined): boolean {
  return value !== false
}

export function isOAuthNotConfiguredError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const code = 'code' in err ? String((err as { code?: unknown }).code || '') : ''
  if (code === OAUTH_NOT_CONFIGURED) return true
  return err instanceof Error && /Microsoft OAuth is not configured/i.test(err.message)
}

export function sourceIsConfigured(value: boolean | null | undefined): boolean {
  return value !== false
}

export function isSourceNotConfiguredError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const code = 'code' in err ? String((err as { code?: unknown }).code || '') : ''
  if (code === SOURCE_NOT_CONFIGURED) return true
  return err instanceof Error && /is not configured\. Add a board token/i.test(err.message)
}

export function sourceUnconfiguredCopy(source: 'greenhouse' | 'lever'): string {
  const name = source === 'greenhouse' ? 'Greenhouse' : 'Lever'
  return `No ${name} board is configured. Add a board token or public board URL, then turn this source on.`
}

export const OAUTH_MESSAGE_TYPE = 'ajas-ms-oauth'
