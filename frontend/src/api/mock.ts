import type { ResumeApi, ResumeDetail, ResumeListItem } from './types'
import { editorIsReady } from '../lib/validation'

type Row = ResumeDetail & { blob?: Blob }

const rows = new Map<string, Row>()
const files = new Map<string, Blob>()
const selections = new Map<string, { runId: string; resumeId: string; effectiveAt: string }>()
const timers = new Map<string, number>()

function now() {
  return new Date().toISOString()
}

function toList(row: Row): ResumeListItem {
  return {
    id: row.id,
    fileName: row.fileName,
    mimeType: row.mimeType,
    size: row.size,
    status: row.status,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    lastParseAt: row.lastParseAt,
    fileHash: row.fileHash,
    validated: row.validated,
  }
}

function parseSoon(id: string) {
  const existing = timers.get(id)
  if (existing) window.clearTimeout(existing)
  const handle = window.setTimeout(() => {
    const row = rows.get(id)
    if (!row || row.status === 'deleted') return
    row.status = 'parsed'
    row.lastParseAt = now()
    row.updatedAt = now()
    if (!row.skills.length) row.skills = ['Python']
    row.validated = editorIsReady({
      contact: row.contact || {},
      experience: row.experience,
      education: row.education,
    })
    rows.set(id, { ...row })
  }, 1500)
  timers.set(id, handle)
}

export const mockApi: ResumeApi = {
  async list() {
    return [...rows.values()]
      .filter((r) => r.status !== 'deleted')
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      .map(toList)
  },
  async get(id) {
    const row = rows.get(id)
    if (!row || row.status === 'deleted') throw new Error('Not found')
    return structuredClone(row)
  },
  async upload(file) {
    const id = crypto.randomUUID()
    const stamp = now()
    const buffer = await file.arrayBuffer()
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer)
    const fileHash = [...new Uint8Array(hashBuffer)].map((b) => b.toString(16).padStart(2, '0')).join('')
    const row: Row = {
      id,
      fileName: file.name,
      mimeType: file.type || 'application/pdf',
      size: file.size,
      status: 'parsing',
      createdAt: stamp,
      updatedAt: stamp,
      lastParseAt: null,
      fileHash,
      validated: false,
      skills: [],
      experience: [],
      education: [],
      contact: { fullName: file.name.replace(/\.[^.]+$/, '') },
      lastParseError: null,
    }
    rows.set(id, row)
    files.set(id, file)
    parseSoon(id)
    return { id, status: 'uploaded' }
  },
  async patch(id, body) {
    const row = rows.get(id)
    if (!row || row.status === 'deleted') throw new Error('Not found')
    if (body.skills) row.skills = body.skills
    if (body.experience) row.experience = body.experience
    if (body.education) row.education = body.education
    if (body.contact) row.contact = body.contact
    row.updatedAt = now()
    row.validated = editorIsReady({
      contact: row.contact || {},
      experience: row.experience,
      education: row.education,
    })
    if (row.status === 'parse_failed' && row.validated) row.status = 'parsed'
    if (row.status === 'parsed' && row.validated) row.status = 'parsed'
    rows.set(id, row)
    return structuredClone(row)
  },
  async remove(id) {
    const row = rows.get(id)
    if (!row) return
    row.status = 'deleted'
    row.updatedAt = now()
    for (const [runId, sel] of [...selections.entries()]) {
      if (sel.resumeId === id) selections.delete(runId)
    }
  },
  async previewUrl(id) {
    const file = files.get(id)
    const row = rows.get(id)
    if (!file || !row || row.status === 'deleted') throw new Error('Not found')
    return URL.createObjectURL(file)
  },
  async retryParse(id) {
    const row = rows.get(id)
    if (!row || row.status === 'deleted') throw new Error('Not found')
    row.status = 'parsing'
    row.lastParseError = null
    row.updatedAt = now()
    parseSoon(id)
  },
  async setActive(runId, resumeId) {
    const row = rows.get(resumeId)
    if (!row || row.status === 'deleted') throw new Error('cannot select a deleted resume')
    const sel = { runId, resumeId, effectiveAt: now() }
    selections.set(runId, sel)
    return sel
  },
  async getActive(runId) {
    return selections.get(runId) ?? null
  },
}

export function seedMockResume(overrides: Partial<ResumeDetail> = {}) {
  const id = overrides.id ?? 'seed-ready'
  const stamp = now()
  rows.set(id, {
    id,
    fileName: 'jane-doe.pdf',
    mimeType: 'application/pdf',
    size: 12000,
    status: 'parsed',
    createdAt: stamp,
    updatedAt: stamp,
    lastParseAt: stamp,
    fileHash: 'abc123',
    validated: true,
    skills: ['Python', 'Azure'],
    experience: [
      {
        title: 'Engineer',
        company: 'Acme',
        startDate: '2020-01',
        endDate: '2022-06',
        description: 'Built APIs',
      },
    ],
    education: [{ institution: 'MIT', degree: 'BS', startDate: '2015-09', endDate: '2019-06' }],
    contact: { fullName: 'Jane Doe', email: 'jane@example.com', phone: '+15555550100' },
    lastParseError: null,
    ...overrides,
  })
  files.set(
    id,
    new Blob(
      ['%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'],
      { type: 'application/pdf' },
    ),
  )
}

export function resetMock() {
  rows.clear()
  files.clear()
  selections.clear()
}
