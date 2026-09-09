import { describe, expect, it } from 'vitest'
import {
  apiToPercent,
  clampPercent,
  emailUiState,
  percentToApi,
  previewCopy,
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
  })

  it('shows fewer-matches copy near 100', () => {
    expect(previewCopy(100)).toBe('Fewer matches')
    expect(previewCopy(0)).toBe('More matches')
  })
})
