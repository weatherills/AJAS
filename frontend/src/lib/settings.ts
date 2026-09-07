/** Map Settings Backend JSON (0.10–0.99) to the Frontend PRD slider (0–100). */

export const SLIDER_MIN = 0
export const SLIDER_MAX = 100
export const SLIDER_STEP = 1
export const DEFAULT_PERCENT = 70
export const API_MIN = 0.1
export const API_MAX = 0.99

export type EmailApiStatus = 'disconnected' | 'pending' | 'connected' | 'error'

export type EmailUiState = 'disconnected' | 'connecting' | 'connected' | 'action_required' | 'error'

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
): EmailUiState {
  if (connecting || status === 'pending') return 'connecting'
  if (status === 'connected') return 'connected'
  if (status === 'error' && (errorCode === 'expired' || errorCode === 'revoked')) return 'action_required'
  if (status === 'error') return 'error'
  return 'disconnected'
}

export const OAUTH_MESSAGE_TYPE = 'ajas-ms-oauth'
