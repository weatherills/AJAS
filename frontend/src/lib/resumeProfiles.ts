export type ResumeProfile = {
  profileId: string
  resumeId: string
  label: string
  tags: string[]
}

const KEY = 'ajas.resume.profiles.v1'
const memory = new Map<string, string>()

function read(userId: string): ResumeProfile[] {
  const key = `${KEY}:${userId}`
  let raw: string | null = null
  try {
    if (typeof localStorage !== 'undefined') raw = localStorage.getItem(key)
  } catch {
    raw = memory.get(key) ?? null
  }
  if (!raw) raw = memory.get(key) ?? null
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as ResumeProfile[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function write(userId: string, rows: ResumeProfile[]): ResumeProfile[] {
  const key = `${KEY}:${userId}`
  const payload = JSON.stringify(rows)
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, payload)
    else memory.set(key, payload)
  } catch {
    memory.set(key, payload)
  }
  return rows
}

export function upsertResumeProfile(userId: string, profile: ResumeProfile): ResumeProfile[] {
  const tags = [...new Set(profile.tags.map((tag) => tag.trim().toLowerCase()).filter(Boolean))]
  const stored = { ...profile, tags }
  const next = [...read(userId).filter((item) => item.profileId !== stored.profileId), stored]
  return write(userId, next)
}

export function profilesFor(userId: string, tag?: string): ResumeProfile[] {
  const rows = read(userId)
  if (!tag) return rows
  const needle = tag.trim().toLowerCase()
  return rows.filter((item) => item.tags.includes(needle))
}
