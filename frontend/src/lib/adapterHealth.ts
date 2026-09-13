export type AdapterHealth = {
  source: string
  lastSuccessAt: string | null
  drift: boolean
  muted: boolean
}

const DEFAULT_ROWS: AdapterHealth[] = [
  { source: 'greenhouse', lastSuccessAt: '2026-09-13T05:00:00Z', drift: false, muted: false },
  { source: 'lever', lastSuccessAt: '2026-09-13T04:50:00Z', drift: false, muted: false },
  { source: 'workday', lastSuccessAt: null, drift: true, muted: false },
]

export function adapterHealthRows(rows: AdapterHealth[] = DEFAULT_ROWS): AdapterHealth[] {
  return rows.map((row) => ({ ...row }))
}

export function toggleMute(rows: AdapterHealth[], source: string): AdapterHealth[] {
  return rows.map((row) => (row.source === source ? { ...row, muted: !row.muted } : row))
}
