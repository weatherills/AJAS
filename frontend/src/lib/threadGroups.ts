import type { EmailThread } from '../api/emailTypes'

export type ThreadGroup = { key: string; label: string; items: EmailThread[] }

export function groupThreads(threads: EmailThread[]): ThreadGroup[] {
  const map = new Map<string, EmailThread[]>()
  for (const thread of threads) {
    const key = thread.jobId || 'unlinked'
    const list = map.get(key) || []
    list.push(thread)
    map.set(key, list)
  }
  return [...map.entries()].map(([key, items]) => ({
    key,
    label: items.find((item) => item.jobTitle)?.jobTitle || (key === 'unlinked' ? 'Unlinked' : key),
    items,
  }))
}
