export type AuditRow = { at: string; actor: string; action: string; target: string }

export function filterAudit(
  rows: AuditRow[],
  query: { actor?: string; action?: string; after?: string; before?: string },
): AuditRow[] {
  const actor = (query.actor || '').trim().toLowerCase()
  const action = (query.action || '').trim().toLowerCase()
  const after = query.after ? Date.parse(query.after) : null
  const before = query.before ? Date.parse(query.before) : null
  return rows.filter((row) => {
    if (actor && !row.actor.toLowerCase().includes(actor)) return false
    if (action && !row.action.toLowerCase().includes(action)) return false
    const at = Date.parse(row.at)
    if (after && !Number.isNaN(after) && at < after) return false
    if (before && !Number.isNaN(before) && at > before) return false
    return true
  })
}

export function auditCsv(rows: AuditRow[]): string {
  const header = 'at,actor,action,target'
  const body = rows.map((row) => [row.at, row.actor, row.action, row.target].map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
  return [header, ...body].join('\n')
}
