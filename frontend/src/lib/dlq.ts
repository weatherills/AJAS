export type DlqItem = { id: string; payload: Record<string, unknown>; status: string }

export function redactDlq(payload: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(payload)) {
    if (['authorization', 'password', 'token', 'secret', 'api_key'].includes(key.toLowerCase())) {
      out[key] = '[redacted]'
    } else {
      out[key] = value
    }
  }
  return out
}

export function retryDlq(items: DlqItem[], id: string): DlqItem[] {
  return items.map((item) => (item.id === id ? { ...item, status: 'queued' } : item))
}
