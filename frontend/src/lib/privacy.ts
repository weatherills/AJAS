export type GdprBundle = {
  userId: string
  exportedAt: string
  jobs: unknown[]
  emails: unknown[]
  matches: unknown[]
  resumes: unknown[]
  logs: unknown[]
}

export function buildExportBundle(userId: string): GdprBundle {
  return {
    userId,
    exportedAt: new Date().toISOString(),
    jobs: [],
    emails: [],
    matches: [],
    resumes: [],
    logs: [],
  }
}

export function purgeSummary(bundle: GdprBundle): { deleted: number; userId: string } {
  const deleted =
    bundle.jobs.length +
    bundle.emails.length +
    bundle.matches.length +
    (bundle.resumes?.length || 0) +
    (bundle.logs?.length || 0)
  return { deleted, userId: bundle.userId }
}
