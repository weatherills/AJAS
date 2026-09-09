export type ApiStatus = 'uploaded' | 'parsing' | 'parsed' | 'parse_failed' | 'deleted'

export type ResumeListItem = {
  id: string
  fileName: string
  mimeType: string
  size: number
  status: ApiStatus
  createdAt: string
  updatedAt: string
  lastParseAt: string | null
  fileHash: string
  validated: boolean
}

export type Experience = {
  title?: string | null
  company?: string | null
  location?: string | null
  startDate?: string | null
  endDate?: string | null
  isCurrent?: boolean
  description?: string | null
}

export type Education = {
  institution?: string | null
  degree?: string | null
  field?: string | null
  startDate?: string | null
  endDate?: string | null
  isCurrent?: boolean
  notes?: string | null
}

export type Contact = {
  fullName?: string | null
  email?: string | null
  phone?: string | null
  location?: string | null
  linkedinUrl?: string | null
}

export type ResumeDetail = ResumeListItem & {
  ownerUserId?: string
  lastParseError?: string | null
  skills: string[]
  experience: Experience[]
  education: Education[]
  contact: Contact | null
}

export type ResumeApi = {
  list(): Promise<ResumeListItem[]>
  get(id: string): Promise<ResumeDetail>
  upload(file: File): Promise<{ id: string; status: string }>
  patch(id: string, body: Partial<{ skills: string[]; experience: Experience[]; education: Education[]; contact: Contact }>): Promise<ResumeDetail>
  remove(id: string): Promise<void>
  previewUrl(id: string): Promise<string>
  retryParse(id: string): Promise<void>
  setActive(runId: string, resumeId: string): Promise<{ runId: string; resumeId: string; effectiveAt: string }>
  getActive(runId: string): Promise<{ runId: string; resumeId: string; effectiveAt: string } | null>
}
