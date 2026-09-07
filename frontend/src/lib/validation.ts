import type { Contact, Education, Experience } from '../api/types'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE = /^\+?[0-9()\-\s]{7,20}$/
const HTTPS = /^https:\/\/.+/i
const DATE = /^(\d{4}-\d{2}-\d{2}|\d{4}-\d{2})$/

export type EditorState = {
  contact: Contact
  skills: string[]
  experience: Experience[]
  education: Education[]
}

export type FieldErrors = Record<string, string>

export function validateClientFile(file: File): string | null {
  const name = file.name.toLowerCase()
  const okType =
    file.type === 'application/pdf' ||
    file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    name.endsWith('.pdf') ||
    name.endsWith('.docx')
  if (!okType) return 'Upload a PDF or DOCX resume.'
  if (file.size > 10 * 1024 * 1024) return 'File must be 10 MB or smaller.'
  if (file.size <= 0) return 'File is empty.'
  return null
}

function dateValue(value: string, end = false): number {
  if (/^\d{4}-\d{2}$/.test(value)) {
    const [y, m] = value.split('-').map(Number)
    if (end) return Date.UTC(y, m, 0)
    return Date.UTC(y, m - 1, 1)
  }
  return Date.parse(value)
}

export function validateEditor(state: EditorState): FieldErrors {
  const errors: FieldErrors = {}
  const name = state.contact.fullName?.trim() || ''
  if (!name) errors['contact.fullName'] = 'Full name is required.'
  const email = state.contact.email?.trim() || ''
  const phone = state.contact.phone?.trim() || ''
  if (!email && !phone) errors['contact.email'] = 'Add an email or phone number.'
  if (email && !EMAIL.test(email)) errors['contact.email'] = 'Enter a valid email.'
  if (phone && !PHONE.test(phone)) errors['contact.phone'] = 'Enter a valid phone number.'
  const url = state.contact.linkedinUrl?.trim() || ''
  if (url && !HTTPS.test(url)) errors['contact.linkedinUrl'] = 'Links must start with https://'

  if (state.skills.length > 100) errors.skills = 'At most 100 skills.'
  state.skills.forEach((skill, i) => {
    if (skill.length > 100) errors[`skills.${i}`] = 'Each skill must be 100 characters or fewer.'
  })

  if (!state.experience.length && !state.education.length) {
    errors.experience = 'Add at least one experience or education entry.'
  }

  state.experience.forEach((item, i) => {
    if ((item.title || '').length > 200) errors[`experience.${i}.title`] = 'Max 200 characters.'
    if ((item.company || '').length > 200) errors[`experience.${i}.company`] = 'Max 200 characters.'
    if ((item.description || '').length > 4000) errors[`experience.${i}.description`] = 'Max 4000 characters.'
    const start = item.startDate?.trim()
    const end = item.endDate?.trim()
    if (start && !DATE.test(start)) errors[`experience.${i}.startDate`] = 'Use YYYY-MM or YYYY-MM-DD.'
    if (end && !item.isCurrent && !DATE.test(end)) errors[`experience.${i}.endDate`] = 'Use YYYY-MM or YYYY-MM-DD.'
    if (start && end && !item.isCurrent && dateValue(end, true) < dateValue(start)) {
      errors[`experience.${i}.endDate`] = 'End date must be on or after the start date.'
    }
  })

  state.education.forEach((item, i) => {
    if ((item.institution || '').length > 200) errors[`education.${i}.institution`] = 'Max 200 characters.'
    if ((item.degree || '').length > 200) errors[`education.${i}.degree`] = 'Max 200 characters.'
    const start = item.startDate?.trim()
    const end = item.endDate?.trim()
    if (start && end && !item.isCurrent && DATE.test(start) && DATE.test(end) && dateValue(end, true) < dateValue(start)) {
      errors[`education.${i}.endDate`] = 'End date must be on or after the start date.'
    }
  })

  return errors
}

export function editorIsReady(state: Pick<EditorState, 'contact' | 'experience' | 'education'>): boolean {
  return Object.keys(
    validateEditor({
      contact: state.contact || {},
      skills: [],
      experience: state.experience || [],
      education: state.education || [],
    }),
  ).length === 0
}
