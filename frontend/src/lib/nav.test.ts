import { describe, expect, it } from 'vitest'
import { hashPath, navIsActive } from './nav'

describe('app nav', () => {
  it('treats empty hash as home', () => {
    expect(hashPath('')).toBe('/')
    expect(navIsActive('#/', '')).toBe(true)
    expect(navIsActive('#/jobs', '')).toBe(false)
  })

  it('matches nested resume editor under Resumes', () => {
    expect(navIsActive('#/resumes', '#/resumes/abc/edit')).toBe(true)
    expect(navIsActive('#/apply', '#/apply/req-1')).toBe(true)
    expect(navIsActive('#/jobs', '#/review')).toBe(false)
  })

  it('does not treat /review as home', () => {
    expect(navIsActive('#/', '#/review')).toBe(false)
    expect(navIsActive('#/review', '#/review')).toBe(true)
  })
})
