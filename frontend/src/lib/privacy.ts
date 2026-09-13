export type GdprBundle = {
  userId: string
  exportedAt: string
  jobs: unknown[]
  emails: unknown[]
  matches: unknown[]
}

export function buildExportBundle(userId: string): GdprBundle {
  return {
    userId,
    exportedAt: new Date().toISOString(),
    jobs: [],
    emails: [],
    matches: [],
  }
}

export function purgeSummary(bundle: GdprBundle): { deleted: number; userId: string } {
  const deleted = bundle.jobs.length + bundle.emails.length + bundle.matches.length
  return { deleted, userId: bundle.userId }
}
