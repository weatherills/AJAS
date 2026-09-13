export type QuotaRow = { source: string; fetched: number; errors: number; capped: number; capHit: boolean }

export function dashboardPreview(rows: QuotaRow[] = []): QuotaRow[] {
  const fallback: QuotaRow[] = [
    { source: 'greenhouse', fetched: 12, errors: 0, capped: 0, capHit: false },
    { source: 'lever', fetched: 9, errors: 1, capped: 0, capHit: false },
    { source: 'workday', fetched: 0, errors: 0, capped: 1, capHit: true },
  ]
  return rows.length ? rows : fallback
}
