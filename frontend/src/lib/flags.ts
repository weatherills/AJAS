/** Operator-facing adapter / automation flags. Defaults match backend FLAG_*. */

export const FLAG_DEFAULTS: Record<string, boolean> = {
  greenhouse: true,
  lever: true,
  indeed_adapter: true,
  linkedin_adapter: true,
  linkedin_easy_apply: true,
  greenhouse_harvest: false,
  gmail_adapter: false,
  google_drive: false,
  slack_notify: false,
  glassdoor_adapter: true,
  wellfound_adapter: true,
  workday_adapter: true,
  ziprecruiter_adapter: true,
  hired_adapter: true,
  greenhouse_career_adapter: true,
  lever_career_adapter: true,
  imap_transport: true,
  bulk_auto_apply: true,
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
