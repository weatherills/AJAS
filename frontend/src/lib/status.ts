import type { ApiStatus, ResumeListItem } from '../api/resumeTypes'
import { LAST_READY_KEY } from './runLock'
import { editorIsReady } from './validation'

export type UiStatus = 'Queued' | 'Parsing' | 'Ready' | 'Needs review' | 'Failed'

export function uiStatus(item: Pick<ResumeListItem, 'status' | 'validated'> & { contact?: { fullName?: string | null } | null; experience?: unknown[]; education?: unknown[] }): UiStatus {
  if (item.status === 'parse_failed') return 'Failed'
  if (item.status === 'uploaded') return 'Queued'
  if (item.status === 'parsing') return 'Parsing'
  if (item.status === 'parsed') {
    if (item.validated) return 'Ready'
    if (item.experience && item.education && item.contact) {
      return editorIsReady({
        contact: item.contact,
        experience: item.experience as never,
        education: item.education as never,
      })
        ? 'Ready'
        : 'Needs review'
    }
    return item.validated ? 'Ready' : 'Needs review'
  }
  return 'Queued'
}

export function canSelectForRun(status: UiStatus): boolean {
  return status === 'Ready' || status === 'Needs review'
}

export function isParsing(status: ApiStatus): boolean {
  return status === 'uploaded' || status === 'parsing'
}

export function preselectReady(items: ResumeListItem[]) {
  const last = localStorage.getItem(LAST_READY_KEY)
  if (last && items.some((item) => item.id === last && canSelectForRun(uiStatus(item)))) return last
  const ready = items.find((item) => uiStatus(item) === 'Ready')
  return ready?.id || ''
}
