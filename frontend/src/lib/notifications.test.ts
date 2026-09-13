import { describe, expect, it } from 'vitest'
import { digestCopy, notificationInbox, pushNotification, resetNotifications } from './notifications'

describe('notification center', () => {
  it('stores toasts and builds a digest email', () => {
    resetNotifications()
    pushNotification({ kind: 'match', title: 'New match', body: 'Staff Engineer at Acme' })
    expect(notificationInbox(true)).toHaveLength(1)
    expect(digestCopy()).toContain('Staff Engineer')
  })
})
