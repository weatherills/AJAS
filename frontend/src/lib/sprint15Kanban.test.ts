import { describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS } from './review'
import {
  a11yShortcuts,
  allowlistUpdate,
  bulkDismissWithUndo,
  exportAuditCsv,
  fitSubScoreTooltips,
  forgetPreview,
  groupEvidence,
  loadSelection,
  loadSiteOverrides,
  manualPackageSteps,
  persistSelection,
  restoreDismiss,
  saveSiteOverride,
  shareFilterHref,
  slaWidgets,
  syncSuppressed,
  truncateChip,
  validateOverride,
} from './sprint15Kanban'

describe('sprint 15 kanban helpers', () => {
  it('persists review selection and shareable filter links', () => {
    persistSelection(['a', 'b'])
    expect(loadSelection()).toEqual(['a', 'b'])
    expect(shareFilterHref({ ...DEFAULT_FILTERS, q: 'python', minScore: 70 })).toContain('q=python')
  })

  it('bulk-dismisses with undo copy', () => {
    const snap = bulkDismissWithUndo(['a', 'b', 'c'], ['b'])
    expect(snap.dismissed.map((item) => item.id)).toEqual(['b'])
    expect(snap.snackbar.toLowerCase()).toContain('undo')
    expect(restoreDismiss(snap, ['a', 'c'])).toEqual(['b', 'a', 'c'])
  })

  it('covers a11y, fit subscores, chips, and evidence grouping', () => {
    expect(a11yShortcuts().j).toBe('next')
    expect(fitSubScoreTooltips(1, 1, 1).total).toBe(1)
    expect(truncateChip('Matched Python experience', 8).label).toContain('…')
    expect(groupEvidence(['Python'], ['Go']).missing).toEqual(['Go'])
  })

  it('builds manual package steps and site overrides', () => {
    expect(manualPackageSteps(true)[0].toLowerCase()).toContain('captcha')
    expect(validateOverride({ name: 'Ada' }).missing).toContain('email')
    saveSiteOverride('greenhouse', { name: 'Ada', email: 'a@b.c', resume: 'r1' })
    expect(loadSiteOverrides()[0].site).toBe('greenhouse')
  })

  it('syncs suppression, exports audit, and SLO widgets', () => {
    expect(syncSuppressed(['A@B.c'], [])).toContain('a@b.c')
    expect(syncSuppressed([], ['a@b.c'])).not.toContain('a@b.c')
    expect(exportAuditCsv([{ at: 't', actor: 'ada', action: 'patch', target: 'x' }])).toContain('ada')
    expect(allowlistUpdate('ada', 'jobs.lever.co').hosts).toContain('jobs.lever.co')
    expect(forgetPreview('ada').dryRun).toBe(true)
    expect(slaWidgets(200, 10, 0.95).ok).toBe(true)
  })
})
