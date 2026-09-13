export type FilterOp = 'contains' | 'starts-with' | 'regex'
export type FilterClause = { field: string; op: FilterOp; value: string }

export function matchClause(value: string, op: FilterOp, needle: string): boolean {
  if (op === 'contains') return value.toLowerCase().includes(needle.toLowerCase())
  if (op === 'starts-with') return value.toLowerCase().startsWith(needle.toLowerCase())
  try {
    return new RegExp(needle, 'i').test(value)
  } catch {
    return false
  }
}

export function applyQuery(rows: Array<Record<string, string>>, clauses: FilterClause[]): Array<Record<string, string>> {
  return rows.filter((row) => clauses.every((clause) => matchClause(row[clause.field] || '', clause.op, clause.value)))
}

export function exportCsv(rows: Array<Record<string, string | number>>, columns: string[]): string {
  const header = columns.join(',')
  const body = rows
    .map((row) => columns.map((col) => String(row[col] ?? '')).join(','))
    .join('\n')
  return `${header}\n${body}`
}

export type OfflineAction = { id: string; type: string; payload: unknown }

export function enqueueOffline(queue: OfflineAction[], action: OfflineAction): OfflineAction[] {
  return [...queue, action]
}

export function replayOffline(queue: OfflineAction[]): { remaining: OfflineAction[]; replayed: string[] } {
  return { remaining: [], replayed: queue.map((item) => item.id) }
}

export function tableToCardLayout(width: number): 'table' | 'cards' {
  return width <= 640 ? 'cards' : 'table'
}

export function emptyCopy(kind: 'jobs' | 'matches' | 'email' | 'error'): string {
  if (kind === 'jobs') return 'No jobs yet. Add a Greenhouse or Lever board in Settings.'
  if (kind === 'matches') return 'No matches above your threshold.'
  if (kind === 'email') return 'No recruiter threads yet.'
  return 'Something went wrong. Retry from the banner or home.'
}

export function tourSteps(): { id: string; title: string; href: string }[] {
  return [
    { id: 'resume', title: 'Upload a resume', href: '#/resumes' },
    { id: 'jobs', title: 'Scan a job board', href: '#/jobs' },
    { id: 'review', title: 'Approve a match', href: '#/review' },
    { id: 'help', title: 'Open help', href: '#/help' },
  ]
}

export function searchHelp(
  docs: { id: string; title: string; body: string }[],
  q: string,
): { id: string; title: string; body: string }[] {
  const needle = q.trim().toLowerCase()
  if (!needle) return docs
  return docs.filter((doc) => `${doc.title} ${doc.body}`.toLowerCase().includes(needle))
}

export function labelledBy(id: string): { 'aria-labelledby': string } {
  return { 'aria-labelledby': id }
}

export function changelogEntries(): { version: string; highlights: string[] }[] {
  return [
    { version: '12.0.0', highlights: ['Tenancy', 'Billing', 'Dark mode', 'fr/es locales'] },
    { version: '11.0.0', highlights: ['Career-page fixtures', 'ANN recall', 'Ops mute'] },
  ]
}
