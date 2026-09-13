import { describe, expect, it } from 'vitest'
import { editorIsReady, validateClientFile, validateEditor } from './validation'
import { profilesFor, upsertResumeProfile } from './resumeProfiles'

describe('resume client validation', () => {
  it('rejects unsupported and oversized files', () => {
    expect(validateClientFile(new File(['hi'], 'notes.txt', { type: 'text/plain' }))).toMatch(/PDF or DOCX/)
    const big = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'big.pdf', { type: 'application/pdf' })
    expect(validateClientFile(big)).toMatch(/10 MB/)
    expect(validateClientFile(new File(['ok'], 'jane.pdf', { type: 'application/pdf' }))).toBeNull()
  })

  it('requires a name, contact method, and work or school history', () => {
    const empty = validateEditor({
      contact: { fullName: '' },
      skills: [],
      experience: [],
      education: [],
    })
    expect(empty['contact.fullName']).toBeTruthy()
    expect(empty['contact.email']).toBeTruthy()
    expect(empty.experience).toBeTruthy()
    expect(
      editorIsReady({
        contact: { fullName: 'Jane Doe', email: 'jane@example.com' },
        experience: [{ title: 'Engineer', company: 'Acme', startDate: '2020-01', endDate: '2022-06' }],
        education: [],
      }),
    ).toBe(true)
  })

  it('stores tagged resume profiles per user', () => {
    upsertResumeProfile('ada', { profileId: 'p1', resumeId: 'r1', label: 'Staff backend', tags: ['backend', 'remote'] })
    upsertResumeProfile('ada', { profileId: 'p2', resumeId: 'r2', label: 'Frontend', tags: ['frontend'] })
    expect(profilesFor('ada')).toHaveLength(2)
    expect(profilesFor('ada', 'remote').map((item) => item.label)).toEqual(['Staff backend'])
  })
})
