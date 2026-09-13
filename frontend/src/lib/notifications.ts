export type AppNotification = { id: string; kind: string; title: string; body: string; read: boolean }

const memory: AppNotification[] = []

export function pushNotification(input: Omit<AppNotification, 'id' | 'read'> & { id?: string }): AppNotification {
  const item: AppNotification = {
    id: input.id || `ntf-${memory.length + 1}`,
    kind: input.kind,
    title: input.title,
    body: input.body,
    read: false,
  }
  memory.unshift(item)
  return item
}

export function notificationInbox(unreadOnly = false): AppNotification[] {
  return unreadOnly ? memory.filter((item) => !item.read) : [...memory]
}

export function markNotificationRead(id: string): void {
  const item = memory.find((row) => row.id === id)
  if (item) item.read = true
}

export function digestCopy(): string {
  const unread = notificationInbox(true)
  if (!unread.length) return "You're caught up."
  return unread.map((item) => `${item.title}: ${item.body}`).join('\n')
}

export function resetNotifications(): void {
  memory.length = 0
}
