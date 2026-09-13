/** Operator-facing adapter / automation flags. Defaults match backend FLAG_*. */

export const FLAG_DEFAULTS: Record<string, boolean> = {
  greenhouse: true,
  lever: true,
  indeed_adapter: false,
  linkedin_adapter: false,
  glassdoor_adapter: false,
  wellfound_adapter: false,
  workday_adapter: false,
  ziprecruiter_adapter: false,
  hired_adapter: false,
  greenhouse_career_adapter: false,
  lever_career_adapter: false,
  imap_transport: false,
  bulk_auto_apply: false,
  ltr_logging: true,
  respect_robots: true,
  site_policy_consent: false,
  data_retention_purge: true,
  gap_penalty: true,
  stack_boost: true,
  fair_norm: true,
  ann_recall: false,
}

export function mergeFlags(overrides: Record<string, boolean> | null | undefined): Record<string, boolean> {
  return { ...FLAG_DEFAULTS, ...(overrides || {}) }
}

export function flagRows(flags: Record<string, boolean>): { id: string; on: boolean }[] {
  return Object.entries(flags).map(([id, on]) => ({ id, on }))
}
