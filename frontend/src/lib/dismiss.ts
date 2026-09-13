/** Undoable bulk dismiss for job cards. */

export type DismissedJob = { id: string; title?: string }

export type DismissSnapshot = {
  remaining: string[]
  dismissed: DismissedJob[]
}

export function bulkDismiss(ids: string[], selected: string[]): DismissSnapshot {
  const drop = new Set(selected)
  return {
    remaining: ids.filter((id) => !drop.has(id)),
    dismissed: selected.filter((id) => ids.includes(id)).map((id) => ({ id })),
  }
}

export function undoDismiss(snapshot: DismissSnapshot, current: string[]): string[] {
  const seen = new Set(current)
  const restored = snapshot.dismissed.map((item) => item.id).filter((id) => !seen.has(id))
  return [...restored, ...current]
}

export function dismissSnackbar(count: number): string {
  if (count <= 0) return 'Nothing dismissed'
  if (count === 1) return 'Dismissed 1 job. Undo?'
  return `Dismissed ${count} jobs. Undo?`
}
