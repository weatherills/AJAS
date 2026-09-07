export const RUN_LOCK_KEY = 'ajas_run_in_progress'
export const LAST_READY_KEY = 'ajas_last_ready_resume'

export function isRunInProgress(resumeId: string): boolean {
  try {
    return localStorage.getItem(RUN_LOCK_KEY) === resumeId
  } catch {
    return false
  }
}
