import { describe, expect, it } from 'vitest'
import { rowActions } from './quickActions'

describe('job list quick actions', () => {
  it('offers apply, dismiss, save, and compare', () => {
    expect(rowActions().map((row) => row.id)).toEqual(['apply', 'dismiss', 'save', 'compare'])
  })
})
