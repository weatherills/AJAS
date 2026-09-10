import { describe, expect, it } from 'vitest'
import {
  apiToPercent,
  clampPercent,
  emailUiState,
  isOAuthNotConfiguredError,
  isSourceNotConfiguredError,
  oauthIsConfigured,
  percentToApi,
  previewCopy,
  sourceIsConfigured,
  sourceUnconfiguredCopy,
} from './settings'

describe('settings mapping', () => {
  it('converts the default 70% to API 0.7', () => {
    expect(percentToApi(70)).toBe(0.7)
    expect(apiToPercent(0.7)).toBe(70)
  })

  it('clamps API writes into 0.10–0.99', () => {
    expect(percentToApi(0)).toBe(0.1)
    expect(percentToApi(100)).toBe(0.99)
    expect(percentToApi(85)).toBe(0.85)
  })

  it('ignores non-numeric slider input', () => {
    expect(clampPercent(Number.NaN)).toBe(70)
    expect(clampPercent(Number.POSITIVE_INFINITY)).toBe(70)
  })

  it('maps email API statuses to UI states', () => {
    expect(emailUiState('disconnected')).toBe('disconnected')
    expect(emailUiState('pending')).toBe('connecting')
    expect(emailUiState('connected')).toBe('connected')
    expect(emailUiState('error', 'expired')).toBe('action_required')
    expect(emailUiState('error', 'GRAPH_ERROR')).toBe('error')
    expect(emailUiState('disconnected', null, true)).toBe('connecting')
    expect(emailUiState('disconnected', null, false, false)).toBe('unconfigured')
    expect(emailUiState('connected', null, false, false)).toBe('connected')
    expect(emailUiState('error', 'expired', false, false)).toBe('unconfigured')
  })

  it('treats oauthConfigured false as unconfigured, missing as configured', () => {
    expect(oauthIsConfigured(false)).toBe(false)
    expect(oauthIsConfigured(true)).toBe(true)
    expect(oauthIsConfigured(undefined)).toBe(true)
  })

  it('treats sourceConfigured false as unconfigured, missing as configured', () => {
    expect(sourceIsConfigured(false)).toBe(false)
    expect(sourceIsConfigured(true)).toBe(true)
    expect(sourceIsConfigured(undefined)).toBe(true)
  })

  it('detects OAuth-not-configured API errors without treating them as generic failures', () => {
    expect(isOAuthNotConfiguredError({ code: 'OAUTH_NOT_CONFIGURED', message: 'Microsoft OAuth is not configured' })).toBe(
      true,
    )
    expect(isOAuthNotConfiguredError(new Error('Microsoft OAuth is not configured'))).toBe(true)
    expect(isOAuthNotConfiguredError(new Error('Request failed (400)'))).toBe(false)
  })

  it('detects source-not-configured API errors and keeps add-tenant copy', () => {
    expect(
      isSourceNotConfiguredError({
        code: 'SOURCE_NOT_CONFIGURED',
        message: 'Greenhouse is not configured. Add a board token before turning this source on, or Job Feed stays empty.',
      }),
    ).toBe(true)
    expect(
      isSourceNotConfiguredError(
        new Error('Lever is not configured. Add a board token before turning this source on, or Job Feed stays empty.'),
      ),
    ).toBe(true)
    expect(isSourceNotConfiguredError(new Error('Couldn’t save source toggle. Try again.'))).toBe(false)
    expect(sourceUnconfiguredCopy('greenhouse')).toMatch(/board token/i)
    expect(sourceUnconfiguredCopy('lever')).toMatch(/Lever/)
  })

  it('shows fewer-matches copy near 100', () => {
    expect(previewCopy(100)).toBe('Fewer matches')
    expect(previewCopy(0)).toBe('More matches')
  })
})
