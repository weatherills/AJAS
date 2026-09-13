export type RowAction = 'apply' | 'dismiss' | 'save' | 'compare'

export function rowActions(): { id: RowAction; label: string }[] {
  return [
    { id: 'apply', label: 'Apply' },
    { id: 'dismiss', label: 'Dismiss' },
    { id: 'save', label: 'Save' },
    { id: 'compare', label: 'Compare' },
  ]
}
