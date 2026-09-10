import { describe, expect, it, vi } from 'vitest'
import { trapFocus } from './focusTrap'

describe('trapFocus', () => {
  it('cycles Tab from the last control back to the first', () => {
    const first = { focus: vi.fn() } as unknown as HTMLElement
    const last = { focus: vi.fn() } as unknown as HTMLElement
    const container = {
      querySelectorAll: () => [first, last],
    } as unknown as HTMLElement
    const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { activeElement: last },
    })
    const event = { key: 'Tab', shiftKey: false, preventDefault: vi.fn() } as unknown as KeyboardEvent
    trapFocus(container, event)
    expect(event.preventDefault).toHaveBeenCalled()
    expect(first.focus).toHaveBeenCalled()
    if (original) Object.defineProperty(globalThis, 'document', original)
    else delete (globalThis as { document?: unknown }).document
  })
})
