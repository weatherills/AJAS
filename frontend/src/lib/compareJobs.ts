export type CompareRow = {
  id: string
  title: string
  company: string
  location: string
  employmentType: string
  score: number | null
}

export function compareRows(
  jobs: Array<{
    id: string
    title: string
    company: string
    location: string
    employmentType?: string | null
  }>,
  matches: Record<string, { score?: number | null } | undefined>,
): CompareRow[] {
  return jobs.map((job) => ({
    id: job.id,
    title: job.title,
    company: job.company,
    location: job.location,
    employmentType: job.employmentType || '',
    score: matches[job.id]?.score ?? null,
  }))
}

export function toggleCompareId(ids: string[], id: string, limit = 3): string[] {
  if (ids.includes(id)) return ids.filter((item) => item !== id)
  if (ids.length >= limit) return [...ids.slice(1), id]
  return [...ids, id]
}
